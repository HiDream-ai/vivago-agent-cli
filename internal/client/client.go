package client

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/attachment"
	"github.com/HiDream-ai/vivago-agent-cli/internal/sse"
)

type TokenProvider interface {
	AccessToken(context.Context) (string, error)
}

type AttachmentUploader interface {
	Put(context.Context, string, string, attachment.Attachment) error
}

type BusinessError struct {
	Code    any
	Message string
}

type HTTPError struct {
	StatusCode int
}

func (err *HTTPError) Error() string {
	return fmt.Sprintf("VivagoAgent request failed with HTTP %d", err.StatusCode)
}

func (err *BusinessError) Error() string {
	return fmt.Sprintf("VivagoAgent error %v: %s", err.Code, err.Message)
}

type Config struct {
	BaseURL        string
	HTTPClient     *http.Client
	TokenProvider  TokenProvider
	Metadata       Metadata
	RequestTimeout time.Duration
	Uploader       AttachmentUploader
}

type Client struct {
	baseURL        string
	httpClient     *http.Client
	tokenProvider  TokenProvider
	metadata       Metadata
	requestTimeout time.Duration
	uploader       AttachmentUploader
}

type AgentStream struct {
	ConversationID string
	TurnID         string
	Decoder        *sse.Decoder
	body           io.ReadCloser
}

func (stream *AgentStream) Close() error {
	if stream.body == nil {
		return nil
	}
	return stream.body.Close()
}

func New(config Config) (*Client, error) {
	if strings.TrimSpace(config.BaseURL) == "" {
		return nil, fmt.Errorf("base URL is required")
	}
	if config.HTTPClient == nil {
		return nil, fmt.Errorf("HTTP client is required")
	}
	if config.TokenProvider == nil {
		return nil, fmt.Errorf("token provider is required")
	}
	requestTimeout := config.RequestTimeout
	if requestTimeout <= 0 {
		requestTimeout = 60 * time.Second
	}
	return &Client{
		baseURL:        strings.TrimRight(config.BaseURL, "/"),
		httpClient:     config.HTTPClient,
		tokenProvider:  config.TokenProvider,
		metadata:       config.Metadata,
		requestTimeout: requestTimeout,
		uploader:       config.Uploader,
	}, nil
}

func (client *Client) CreateProject(ctx context.Context, name string) (map[string]any, error) {
	return client.postJSON(ctx, "/api/agent/v1/project/create", map[string]any{
		"name":    name,
		"version": "v2",
	})
}

func (client *Client) ListProjects(ctx context.Context, pageNumber, pageSize int) (map[string]any, error) {
	return client.postJSON(ctx, "/api/agent/v1/project/list", map[string]any{
		"page_no":   pageNumber,
		"page_size": pageSize,
	})
}

func (client *Client) ProjectDetail(ctx context.Context, projectID string) (map[string]any, error) {
	return client.postJSON(ctx, "/api/agent/v1/project/detail", map[string]any{
		"project_id": projectID,
	})
}

func (client *Client) ListProjectAssets(
	ctx context.Context,
	offset *int,
	pageSize int,
) (map[string]any, error) {
	return client.postJSON(ctx, "/api/agent/v1/project_asset_list", map[string]any{
		"offset":    offset,
		"page_size": pageSize,
	})
}

func (client *Client) Cancel(ctx context.Context, conversationID, turnID string) (map[string]any, error) {
	return client.postJSON(ctx, "/api/agent/v2/conversation/cancel", map[string]any{
		"conversation_id": conversationID,
		"turn_id":         turnID,
	})
}

func (client *Client) History(
	ctx context.Context,
	conversationID string,
	pageNumber, pageSize int,
) (map[string]any, error) {
	return client.postJSON(ctx, "/api/agent/v2/conversation/history", map[string]any{
		"conversation_id": conversationID,
		"page_no":         pageNumber,
		"page_size":       pageSize,
	})
}

func (client *Client) Ask(
	ctx context.Context,
	prompt, projectID, conversationID string,
	imageSearchEnabled bool,
	filePaths ...string,
) (*AgentStream, error) {
	prompt = strings.TrimSpace(prompt)
	projectID = strings.TrimSpace(projectID)
	conversationID = strings.TrimSpace(conversationID)
	if prompt == "" {
		return nil, fmt.Errorf("prompt is required")
	}
	if (projectID == "") == (conversationID == "") {
		return nil, fmt.Errorf("exactly one of project ID or conversation ID is required")
	}
	attachments, err := attachment.Validate(filePaths)
	if err != nil {
		return nil, err
	}
	if len(attachments) > 0 && client.uploader == nil {
		return nil, fmt.Errorf("attachment uploader is unavailable")
	}

	resolvedConversationID := conversationID
	if projectID != "" {
		var err error
		resolvedConversationID, err = client.projectConversationID(ctx, projectID)
		if err != nil {
			return nil, err
		}
	}
	messageID, err := newMessageID()
	if err != nil {
		return nil, err
	}
	content := []any{map[string]any{"type": "text", "text": prompt}}
	for _, item := range attachments {
		key, err := client.uploadAttachment(ctx, item)
		if err != nil {
			return nil, err
		}
		content = append(content, map[string]any{
			"type": item.MediaType,
			"source": map[string]any{
				"type":  "url",
				"value": key,
			},
			"name": item.Name,
		})
	}
	body := map[string]any{
		"threadId": resolvedConversationID,
		"runId":    "",
		"state":    map[string]any{},
		"messages": []any{
			map[string]any{
				"id":      messageID,
				"role":    "user",
				"content": content,
			},
		},
		"tools":          []any{},
		"context":        []any{},
		"forwardedProps": map[string]any{},
	}
	if resolvedConversationID == "" {
		body["projectId"] = projectID
	}
	if imageSearchEnabled {
		body["imageSearchEnabled"] = true
	}
	return client.StartChat(ctx, body)
}

func (client *Client) uploadAttachment(
	ctx context.Context,
	item attachment.Attachment,
) (string, error) {
	key, err := newAttachmentKey(item)
	if err != nil {
		return "", err
	}
	response, err := client.getJSON(
		ctx,
		"/prod-api/user/google_key/"+url.PathEscape(item.Bucket),
		url.Values{"filename": {key}, "content_type": {item.ContentType}},
	)
	if err != nil {
		return "", err
	}
	uploadURL, ok := response["result"].(string)
	if !ok || strings.TrimSpace(uploadURL) == "" {
		return "", fmt.Errorf("upload credential response is missing result")
	}
	if err := client.uploader.Put(ctx, uploadURL, key, item); err != nil {
		return "", err
	}
	return key, nil
}

func newAttachmentKey(item attachment.Attachment) (string, error) {
	identifier, err := newMessageID()
	if err != nil {
		return "", err
	}
	if item.MediaType == "image" {
		prefix := "p"
		if item.Suffix == ".jpg" || item.Suffix == ".jpeg" {
			prefix = "j"
		}
		return prefix + "_" + identifier, nil
	}
	return identifier + item.Suffix, nil
}

func (client *Client) Resume(ctx context.Context, turnID, lastEventID string) (*AgentStream, error) {
	turnID = strings.TrimSpace(turnID)
	lastEventID = strings.TrimSpace(lastEventID)
	if turnID == "" {
		return nil, fmt.Errorf("turn ID is required")
	}
	body := map[string]any{
		"threadId":       "",
		"runId":          "",
		"state":          map[string]any{},
		"messages":       []any{},
		"tools":          []any{},
		"context":        []any{},
		"forwardedProps": map[string]any{},
		"turnId":         turnID,
	}
	if lastEventID != "" {
		body["lastEventId"] = lastEventID
	}
	stream, err := client.StartChat(ctx, body)
	if err != nil {
		return nil, err
	}
	if stream.TurnID == "" {
		stream.TurnID = turnID
	}
	return stream, nil
}

func (client *Client) projectConversationID(ctx context.Context, projectID string) (string, error) {
	response, err := client.ProjectDetail(ctx, projectID)
	if err != nil {
		return "", err
	}
	data, ok := response["data"].(map[string]any)
	if !ok {
		return "", fmt.Errorf("project detail response is missing data")
	}
	rawConversations, ok := data["conversations"].([]any)
	if !ok {
		return "", fmt.Errorf("project detail response is missing conversations")
	}
	conversations := make([]string, 0, len(rawConversations))
	for _, value := range rawConversations {
		conversationID, ok := value.(string)
		if !ok || strings.TrimSpace(conversationID) == "" {
			continue
		}
		conversations = append(conversations, strings.TrimSpace(conversationID))
	}
	if len(conversations) > 1 {
		return "", &BusinessError{
			Code: "PROJECT_CONVERSATION_CONFLICT",
			Message: fmt.Sprintf(
				"project %s already has %d conversations; one project may have only one conversation",
				projectID,
				len(conversations),
			),
		}
	}
	if len(conversations) == 1 {
		return conversations[0], nil
	}
	return "", nil
}

func newMessageID() (string, error) {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return "", fmt.Errorf("generate message ID: %w", err)
	}
	value[6] = (value[6] & 0x0f) | 0x40
	value[8] = (value[8] & 0x3f) | 0x80
	return fmt.Sprintf(
		"%08x-%04x-%04x-%04x-%012x",
		value[0:4],
		value[4:6],
		value[6:8],
		value[8:10],
		value[10:16],
	), nil
}

func (client *Client) StartChat(ctx context.Context, body map[string]any) (*AgentStream, error) {
	encoded, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("encode request: %w", err)
	}
	token, err := client.tokenProvider.AccessToken(ctx)
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		client.baseURL+"/api/agent/v2/conversation/chat",
		bytes.NewReader(encoded),
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	request.Header = RequestHeaders(token, client.metadata)
	request.Header.Set("Accept", "text/event-stream")

	response, err := client.httpClient.Do(request)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		_ = response.Body.Close()
		return nil, &HTTPError{StatusCode: response.StatusCode}
	}
	return &AgentStream{
		ConversationID: response.Header.Get("X-Vivago-Conversation-Id"),
		TurnID:         response.Header.Get("X-Vivago-Turn-Id"),
		Decoder:        sse.NewDecoder(response.Body),
		body:           response.Body,
	}, nil
}

func (client *Client) postJSON(ctx context.Context, path string, body map[string]any) (map[string]any, error) {
	encoded, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("encode request: %w", err)
	}
	requestContext, cancel := context.WithTimeout(ctx, client.requestTimeout)
	defer cancel()
	token, err := client.tokenProvider.AccessToken(requestContext)
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequestWithContext(
		requestContext,
		http.MethodPost,
		client.baseURL+path,
		bytes.NewReader(encoded),
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	request.Header = RequestHeaders(token, client.metadata)

	response, err := client.httpClient.Do(request)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return nil, &HTTPError{StatusCode: response.StatusCode}
	}

	var decoded map[string]any
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	if code := decoded["code"]; code != nil && code != float64(0) {
		message, _ := decoded["message"].(string)
		if message == "" {
			message = "request failed"
		}
		return nil, &BusinessError{Code: code, Message: message}
	}
	return decoded, nil
}

func (client *Client) getJSON(
	ctx context.Context,
	path string,
	query url.Values,
) (map[string]any, error) {
	requestContext, cancel := context.WithTimeout(ctx, client.requestTimeout)
	defer cancel()
	token, err := client.tokenProvider.AccessToken(requestContext)
	if err != nil {
		return nil, err
	}
	requestURL := client.baseURL + path
	if encodedQuery := query.Encode(); encodedQuery != "" {
		requestURL += "?" + encodedQuery
	}
	request, err := http.NewRequestWithContext(requestContext, http.MethodGet, requestURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	request.Header = RequestHeaders(token, client.metadata)
	response, err := client.httpClient.Do(request)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return nil, &HTTPError{StatusCode: response.StatusCode}
	}
	var decoded map[string]any
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	if code := decoded["code"]; code != nil && code != float64(0) {
		message, _ := decoded["message"].(string)
		if message == "" {
			message = "request failed"
		}
		return nil, &BusinessError{Code: code, Message: message}
	}
	return decoded, nil
}
