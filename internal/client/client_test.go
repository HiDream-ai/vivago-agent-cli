package client

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/attachment"
)

type staticTokenProvider struct {
	token string
}

func TestCreateProjectReturnsStructuredBusinessError(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       io.NopCloser(strings.NewReader(`{"code":"PROJECT_LIMIT","message":"project limit reached","data":null}`)),
			Request:    request,
		}, nil
	})}
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata:      Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	_, err = api.CreateProject(context.Background(), "Too many")
	var businessError *BusinessError
	if !errors.As(err, &businessError) {
		t.Fatalf("error = %v, want BusinessError", err)
	}
	if businessError.Code != "PROJECT_LIMIT" {
		t.Fatalf("server code = %#v", businessError.Code)
	}
	if businessError.Message != "project limit reached" {
		t.Fatalf("message = %q", businessError.Message)
	}
}

func TestCreateProjectReturnsRedactedHTTPError(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusUnauthorized,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       io.NopCloser(strings.NewReader(`{"message":"rejected test-ticket"}`)),
			Request:    request,
		}, nil
	})}
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata:      Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	_, err = api.CreateProject(context.Background(), "unauthorized")
	var httpError *HTTPError
	if !errors.As(err, &httpError) || httpError.StatusCode != http.StatusUnauthorized {
		t.Fatalf("error = %v, want HTTPError 401", err)
	}
	if strings.Contains(err.Error(), "test-ticket") {
		t.Fatalf("HTTP error leaked response or token: %v", err)
	}
}

func (p staticTokenProvider) AccessToken(context.Context) (string, error) {
	return p.token, nil
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (function roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}

func TestCreateProjectUsesWebV1Contract(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.Method != http.MethodPost {
			t.Errorf("method = %s, want POST", request.Method)
		}
		if request.URL.Path != "/api/agent/v1/project/create" {
			t.Errorf("path = %q", request.URL.Path)
		}
		if request.Header.Get("Authorization") != "Bearer test-ticket" {
			t.Errorf("authorization header was not set")
		}
		if request.Header.Get("X-Source") != "cli" {
			t.Errorf("X-Source = %q, want cli", request.Header.Get("X-Source"))
		}
		if request.Header.Get("X-Client-Platform") != "web" {
			t.Errorf("X-Client-Platform = %q, want web", request.Header.Get("X-Client-Platform"))
		}

		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if body["name"] != "Codex task" || body["version"] != "v2" {
			t.Errorf("body = %#v", body)
		}

		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       io.NopCloser(strings.NewReader(`{"code":0,"data":{"project_id":"p-1"}}`)),
			Request:    request,
		}, nil
	})}

	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata: Metadata{
			Version: "0.3.0-dev",
			OS:      "darwin",
			Arch:    "arm64",
			Host:    "codex",
		},
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	response, err := api.CreateProject(context.Background(), "Codex task")
	if err != nil {
		t.Fatalf("create project: %v", err)
	}
	data, ok := response["data"].(map[string]any)
	if !ok || data["project_id"] != "p-1" {
		t.Fatalf("response = %#v", response)
	}
}

func TestListProjectsUsesWebV1Contract(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.Method != http.MethodPost || request.URL.Path != "/api/agent/v1/project/list" {
			t.Errorf("request = %s %s", request.Method, request.URL.Path)
		}
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if body["page_no"] != float64(2) || body["page_size"] != float64(10) {
			t.Errorf("body = %#v", body)
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       io.NopCloser(strings.NewReader(`{"code":0,"data":{"projects":[]}}`)),
			Request:    request,
		}, nil
	})}
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata:      Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	response, err := api.ListProjects(context.Background(), 2, 10)
	if err != nil {
		t.Fatalf("list projects: %v", err)
	}
	if response["code"] != float64(0) {
		t.Fatalf("response = %#v", response)
	}
}

func TestJSONRequestsUseConfiguredTimeout(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		<-request.Context().Done()
		return nil, request.Context().Err()
	})}
	api, err := New(Config{
		BaseURL:        "https://dev.vivago.ai",
		HTTPClient:     httpClient,
		TokenProvider:  staticTokenProvider{token: "test-ticket"},
		Metadata:       Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
		RequestTimeout: 20 * time.Millisecond,
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	started := time.Now()
	_, err = api.CreateProject(context.Background(), "timeout")
	if err == nil || time.Since(started) > time.Second {
		t.Fatalf("error = %v, elapsed = %s", err, time.Since(started))
	}
}

func TestStartChatUsesWebV2SSEContractAndExposesSessionIDs(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.Method != http.MethodPost || request.URL.Path != "/api/agent/v2/conversation/chat" {
			t.Errorf("request = %s %s", request.Method, request.URL.Path)
		}
		if request.Header.Get("Accept") != "text/event-stream" {
			t.Errorf("Accept = %q", request.Header.Get("Accept"))
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header: http.Header{
				"Content-Type":             []string{"text/event-stream"},
				"X-Vivago-Conversation-Id": []string{"c-1"},
				"X-Vivago-Turn-Id":         []string{"t-1"},
			},
			Body:    io.NopCloser(strings.NewReader("id: 1-0\ndata: {\"type\":\"RUN_STARTED\"}\n\n")),
			Request: request,
		}, nil
	})}
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata:      Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	stream, err := api.StartChat(context.Background(), map[string]any{
		"threadId": "",
		"messages": []any{},
	})
	if err != nil {
		t.Fatalf("start chat: %v", err)
	}
	defer stream.Close()
	if stream.ConversationID != "c-1" || stream.TurnID != "t-1" {
		t.Fatalf("session = %#v", stream)
	}
	event, err := stream.Decoder.Decode()
	if err != nil {
		t.Fatalf("decode event: %v", err)
	}
	data, ok := event.Data.(map[string]any)
	if !ok || data["type"] != "RUN_STARTED" {
		t.Fatalf("event data = %#v", event.Data)
	}
}

func TestAskUsesProjectPreflightAndBuildsWebV2Message(t *testing.T) {
	requestNumber := 0
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requestNumber++
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatalf("decode request %d: %v", requestNumber, err)
		}
		switch requestNumber {
		case 1:
			if request.URL.Path != "/api/agent/v1/project/detail" {
				t.Fatalf("preflight path = %q", request.URL.Path)
			}
			if body["project_id"] != "p-1" {
				t.Fatalf("preflight body = %#v", body)
			}
			return jsonResponse(request, `{"code":0,"data":{"id":"p-1","conversations":[]}}`), nil
		case 2:
			if request.URL.Path != "/api/agent/v2/conversation/chat" {
				t.Fatalf("chat path = %q", request.URL.Path)
			}
			if body["threadId"] != "" || body["projectId"] != "p-1" {
				t.Fatalf("routing body = %#v", body)
			}
			messages, ok := body["messages"].([]any)
			if !ok || len(messages) != 1 {
				t.Fatalf("messages = %#v", body["messages"])
			}
			message := messages[0].(map[string]any)
			if !regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`).MatchString(message["id"].(string)) {
				t.Fatalf("message id = %#v", message["id"])
			}
			if message["role"] != "user" {
				t.Fatalf("message = %#v", message)
			}
			content := message["content"].([]any)
			if len(content) != 1 || content[0].(map[string]any)["text"] != "Make a launch plan" {
				t.Fatalf("content = %#v", content)
			}
			return sseResponse(request, "c-1", "t-1"), nil
		default:
			t.Fatalf("unexpected request %d", requestNumber)
			return nil, nil
		}
	})}
	api := newTestClient(t, httpClient)

	stream, err := api.Ask(context.Background(), "Make a launch plan", "p-1", "", false)
	if err != nil {
		t.Fatalf("ask: %v", err)
	}
	defer stream.Close()
	if stream.ConversationID != "c-1" || stream.TurnID != "t-1" {
		t.Fatalf("session = %#v", stream)
	}
}

func TestAskReusesOnlyProjectConversation(t *testing.T) {
	requestNumber := 0
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requestNumber++
		if requestNumber == 1 {
			return jsonResponse(request, `{"code":0,"data":{"conversations":["conversation-existing"]}}`), nil
		}
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["threadId"] != "conversation-existing" {
			t.Fatalf("threadId = %#v", body["threadId"])
		}
		if _, exists := body["projectId"]; exists {
			t.Fatalf("projectId must be omitted: %#v", body)
		}
		return sseResponse(request, "conversation-existing", "t-1"), nil
	})}
	api := newTestClient(t, httpClient)

	stream, err := api.Ask(context.Background(), "Continue", "p-1", "", false)
	if err != nil {
		t.Fatalf("ask: %v", err)
	}
	defer stream.Close()
}

func TestAskEnablesImageSearchAtChatRequestTopLevel(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.URL.Path == "/api/agent/v1/project/detail" {
			return jsonResponse(request, `{"code":0,"data":{"conversations":[]}}`), nil
		}
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["imageSearchEnabled"] != true {
			t.Fatalf("imageSearchEnabled = %#v", body["imageSearchEnabled"])
		}
		if state := body["state"].(map[string]any); state["imageSearchEnabled"] != nil {
			t.Fatalf("imageSearchEnabled must not be nested in state: %#v", body)
		}
		if forwarded := body["forwardedProps"].(map[string]any); forwarded["imageSearchEnabled"] != nil {
			t.Fatalf("imageSearchEnabled must not be nested in forwardedProps: %#v", body)
		}
		return sseResponse(request, "c-1", "t-1"), nil
	})}
	api := newTestClient(t, httpClient)

	stream, err := api.Ask(context.Background(), "Find visual references", "p-1", "", true)
	if err != nil {
		t.Fatalf("ask: %v", err)
	}
	defer stream.Close()
}

func TestAskOmitsImageSearchWhenDisabled(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.URL.Path == "/api/agent/v1/project/detail" {
			return jsonResponse(request, `{"code":0,"data":{"conversations":[]}}`), nil
		}
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if _, exists := body["imageSearchEnabled"]; exists {
			t.Fatalf("imageSearchEnabled must be omitted when disabled: %#v", body)
		}
		return sseResponse(request, "c-1", "t-1"), nil
	})}
	api := newTestClient(t, httpClient)

	stream, err := api.Ask(context.Background(), "Make a cat", "p-1", "", false)
	if err != nil {
		t.Fatalf("ask: %v", err)
	}
	defer stream.Close()
}

func TestAskRejectsMultipleProjectConversationsBeforeChat(t *testing.T) {
	requestCount := 0
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requestCount++
		return jsonResponse(request, `{"code":0,"data":{"conversations":["c-1","c-2"]}}`), nil
	})}
	api := newTestClient(t, httpClient)

	_, err := api.Ask(context.Background(), "Do not duplicate", "p-1", "", false)
	var businessError *BusinessError
	if !errors.As(err, &businessError) || businessError.Code != "PROJECT_CONVERSATION_CONFLICT" {
		t.Fatalf("error = %#v", err)
	}
	if requestCount != 1 {
		t.Fatalf("request count = %d, want preflight only", requestCount)
	}
}

func TestAskValidatesRoutingBeforeNetwork(t *testing.T) {
	requestCount := 0
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requestCount++
		return nil, errors.New("unexpected request")
	})}
	api := newTestClient(t, httpClient)

	for _, testCase := range []struct {
		prompt, projectID, conversationID string
	}{
		{prompt: "", projectID: "p-1"},
		{prompt: "hello"},
		{prompt: "hello", projectID: "p-1", conversationID: "c-1"},
	} {
		if _, err := api.Ask(context.Background(), testCase.prompt, testCase.projectID, testCase.conversationID, false); err == nil {
			t.Fatalf("Ask(%q, %q, %q) succeeded", testCase.prompt, testCase.projectID, testCase.conversationID)
		}
	}
	if requestCount != 0 {
		t.Fatalf("request count = %d", requestCount)
	}
}

func TestResumeUsesTurnAndCursorWithoutResubmittingPrompt(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["turnId"] != "t-original" || body["lastEventId"] != "42-0" {
			t.Fatalf("resume routing = %#v", body)
		}
		messages, ok := body["messages"].([]any)
		if !ok || len(messages) != 0 {
			t.Fatalf("resume messages = %#v", body["messages"])
		}
		return sseResponse(request, "c-1", ""), nil
	})}
	api := newTestClient(t, httpClient)

	stream, err := api.Resume(context.Background(), "t-original", "42-0")
	if err != nil {
		t.Fatalf("resume: %v", err)
	}
	defer stream.Close()
	if stream.TurnID != "t-original" {
		t.Fatalf("turn id = %q", stream.TurnID)
	}
}

func TestProjectAssetsCancelAndHistoryUseWebContracts(t *testing.T) {
	offset := 123456
	tests := []struct {
		name string
		path string
		body map[string]any
		call func(*Client) error
	}{
		{
			name: "project assets",
			path: "/api/agent/v1/project_asset_list",
			body: map[string]any{"offset": float64(offset), "page_size": float64(50)},
			call: func(api *Client) error {
				_, err := api.ListProjectAssets(context.Background(), &offset, 50)
				return err
			},
		},
		{
			name: "cancel",
			path: "/api/agent/v2/conversation/cancel",
			body: map[string]any{"conversation_id": "c-1", "turn_id": "t-1"},
			call: func(api *Client) error {
				_, err := api.Cancel(context.Background(), "c-1", "t-1")
				return err
			},
		},
		{
			name: "history",
			path: "/api/agent/v2/conversation/history",
			body: map[string]any{
				"conversation_id": "c-1",
				"page_no":         float64(2),
				"page_size":       float64(10),
			},
			call: func(api *Client) error {
				_, err := api.History(context.Background(), "c-1", 2, 10)
				return err
			},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
				if request.URL.Path != testCase.path {
					t.Fatalf("path = %q", request.URL.Path)
				}
				var body map[string]any
				if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
					t.Fatal(err)
				}
				if !reflect.DeepEqual(body, testCase.body) {
					t.Fatalf("body = %#v, want %#v", body, testCase.body)
				}
				return jsonResponse(request, `{"code":0,"data":{}}`), nil
			})}
			if err := testCase.call(newTestClient(t, httpClient)); err != nil {
				t.Fatalf("call: %v", err)
			}
		})
	}
}

func TestProjectAssetsKeepsMissingOffsetAsNull(t *testing.T) {
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		var body map[string]any
		if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if value, exists := body["offset"]; !exists || value != nil {
			t.Fatalf("offset = %#v, exists = %t", value, exists)
		}
		return jsonResponse(request, `{"code":0,"data":{}}`), nil
	})}
	api := newTestClient(t, httpClient)
	if _, err := api.ListProjectAssets(context.Background(), nil, 20); err != nil {
		t.Fatal(err)
	}
}

func TestAskValidatesAndStreamsAttachmentsWithoutPuttingSignedURLInChat(t *testing.T) {
	directory := t.TempDir()
	filePath := filepath.Join(directory, "cat.png")
	if err := os.WriteFile(filePath, []byte("png-bytes"), 0o600); err != nil {
		t.Fatal(err)
	}
	uploader := &fakeAttachmentUploader{}
	requestCount := 0
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requestCount++
		switch requestCount {
		case 1:
			return jsonResponse(request, `{"code":0,"data":{"conversations":[]}}`), nil
		case 2:
			if request.Method != http.MethodGet || request.URL.Path != "/prod-api/user/google_key/hidreamai-image" {
				t.Fatalf("credential request = %s %s", request.Method, request.URL.Path)
			}
			if request.URL.Query().Get("content_type") != "image/png" ||
				!strings.HasPrefix(request.URL.Query().Get("filename"), "p_") {
				t.Fatalf("credential query = %s", request.URL.RawQuery)
			}
			return jsonResponse(request, `{"code":0,"result":"https://upload.example.com/object?secret=signed"}`), nil
		case 3:
			var body map[string]any
			if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			message := body["messages"].([]any)[0].(map[string]any)
			content := message["content"].([]any)
			if len(content) != 2 {
				t.Fatalf("content = %#v", content)
			}
			attachmentContent := content[1].(map[string]any)
			source := attachmentContent["source"].(map[string]any)
			if attachmentContent["type"] != "image" || attachmentContent["name"] != "cat.png" ||
				source["type"] != "url" || source["value"] != uploader.key {
				t.Fatalf("attachment content = %#v", attachmentContent)
			}
			encoded, _ := json.Marshal(body)
			if bytes.Contains(encoded, []byte("upload.example.com")) || bytes.Contains(encoded, []byte("signed")) {
				t.Fatalf("chat body leaked signed URL: %s", encoded)
			}
			return sseResponse(request, "c-1", "t-1"), nil
		default:
			t.Fatalf("unexpected request %d", requestCount)
			return nil, nil
		}
	})}
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata:      Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
		Uploader:      uploader,
	})
	if err != nil {
		t.Fatal(err)
	}

	stream, err := api.Ask(context.Background(), "Use this", "p-1", "", false, filePath)
	if err != nil {
		t.Fatalf("ask: %v", err)
	}
	defer stream.Close()
	if uploader.calls != 1 || uploader.item.Path != filePath || uploader.item.ContentType != "image/png" {
		t.Fatalf("uploader = %#v", uploader)
	}
	if !strings.HasPrefix(uploader.key, "p_") || uploader.uploadURL == "" {
		t.Fatalf("upload key/url = %q / %q", uploader.key, uploader.uploadURL)
	}
}

func TestAskRejectsUnsafeAttachmentBeforeAnyNetworkRequest(t *testing.T) {
	directory := t.TempDir()
	unsafePath := filepath.Join(directory, "archive.zip")
	if err := os.WriteFile(unsafePath, []byte("zip"), 0o600); err != nil {
		t.Fatal(err)
	}
	requestCount := 0
	httpClient := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requestCount++
		return nil, errors.New("unexpected request")
	})}
	uploader := &fakeAttachmentUploader{}
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Uploader:      uploader,
	})
	if err != nil {
		t.Fatal(err)
	}

	if _, err := api.Ask(context.Background(), "Inspect", "p-1", "", false, unsafePath); err == nil {
		t.Fatal("unsafe attachment was accepted")
	}
	if requestCount != 0 || uploader.calls != 0 {
		t.Fatalf("network=%d uploader=%d", requestCount, uploader.calls)
	}
}

func TestNewAttachmentKeyPreservesPilotMediaRules(t *testing.T) {
	tests := []struct {
		item      attachment.Attachment
		prefix    string
		suffix    string
		forbidDot bool
	}{
		{item: attachment.Attachment{MediaType: "image", Suffix: ".jpg"}, prefix: "j_", forbidDot: true},
		{item: attachment.Attachment{MediaType: "image", Suffix: ".png"}, prefix: "p_", forbidDot: true},
		{item: attachment.Attachment{MediaType: "video", Suffix: ".mp4"}, suffix: ".mp4"},
		{item: attachment.Attachment{MediaType: "audio", Suffix: ".mp3"}, suffix: ".mp3"},
		{item: attachment.Attachment{MediaType: "document", Suffix: ".pdf"}, suffix: ".pdf"},
	}
	for _, testCase := range tests {
		key, err := newAttachmentKey(testCase.item)
		if err != nil {
			t.Fatal(err)
		}
		if testCase.prefix != "" && !strings.HasPrefix(key, testCase.prefix) {
			t.Fatalf("key %q missing prefix %q", key, testCase.prefix)
		}
		if testCase.suffix != "" && !strings.HasSuffix(key, testCase.suffix) {
			t.Fatalf("key %q missing suffix %q", key, testCase.suffix)
		}
		if testCase.forbidDot && strings.Contains(key, ".") {
			t.Fatalf("image key contains extension: %q", key)
		}
	}
}

type fakeAttachmentUploader struct {
	calls     int
	uploadURL string
	key       string
	item      attachment.Attachment
}

func (uploader *fakeAttachmentUploader) Put(
	_ context.Context,
	uploadURL, key string,
	item attachment.Attachment,
) error {
	uploader.calls++
	uploader.uploadURL = uploadURL
	uploader.key = key
	uploader.item = item
	return nil
}

func newTestClient(t *testing.T, httpClient *http.Client) *Client {
	t.Helper()
	api, err := New(Config{
		BaseURL:       "https://dev.vivago.ai",
		HTTPClient:    httpClient,
		TokenProvider: staticTokenProvider{token: "test-ticket"},
		Metadata:      Metadata{Version: "dev", OS: "darwin", Arch: "arm64", Host: "codex"},
	})
	if err != nil {
		t.Fatalf("new client: %v", err)
	}
	return api
}

func jsonResponse(request *http.Request, body string) *http.Response {
	return &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"application/json"}},
		Body:       io.NopCloser(strings.NewReader(body)),
		Request:    request,
	}
}

func sseResponse(request *http.Request, conversationID, turnID string) *http.Response {
	return &http.Response{
		StatusCode: http.StatusOK,
		Header: http.Header{
			"Content-Type":             []string{"text/event-stream"},
			"X-Vivago-Conversation-Id": []string{conversationID},
			"X-Vivago-Turn-Id":         []string{turnID},
		},
		Body:    io.NopCloser(strings.NewReader("data: {\"type\":\"RUN_FINISHED\"}\n\n")),
		Request: request,
	}
}
