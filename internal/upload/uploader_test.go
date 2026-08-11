package upload

import (
	"context"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/HiDream-ai/vivago-agent-cli/internal/attachment"
)

func TestPutStreamsRegularFileWithOnlyRequiredHeaders(t *testing.T) {
	path := filepath.Join(t.TempDir(), "clip.mp4")
	payload := []byte("streamed-video-bytes")
	if err := os.WriteFile(path, payload, 0o600); err != nil {
		t.Fatal(err)
	}
	item := attachment.Attachment{
		Path: path, Name: "clip.mp4", Suffix: ".mp4", MediaType: "video",
		Bucket: "hidreamai-media", ContentType: "video/mp4", Size: int64(len(payload)),
	}
	uploader := New(roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.Method != http.MethodPut || request.URL.Hostname() != "upload.example.com" {
			t.Fatalf("request = %s %s", request.Method, request.URL)
		}
		if request.Header.Get("Content-Type") != "video/mp4" || request.ContentLength != int64(len(payload)) {
			t.Fatalf("headers = %#v, length = %d", request.Header, request.ContentLength)
		}
		if request.Header.Get("Authorization") != "" || request.Header.Get("Cookie") != "" {
			t.Fatalf("credential headers leaked to upload host: %#v", request.Header)
		}
		body, err := io.ReadAll(request.Body)
		if err != nil || string(body) != string(payload) {
			t.Fatalf("body = %q, err = %v", body, err)
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{},
			Body:       io.NopCloser(strings.NewReader("")),
			Request:    request,
		}, nil
	}))

	if err := uploader.Put(
		context.Background(),
		"https://upload.example.com/object?signature=secret",
		"v-key.mp4",
		item,
	); err != nil {
		t.Fatalf("put: %v", err)
	}
}

func TestPutRejectsUnsafeURLsBeforeTransport(t *testing.T) {
	path := filepath.Join(t.TempDir(), "cat.png")
	if err := os.WriteFile(path, []byte("png"), 0o600); err != nil {
		t.Fatal(err)
	}
	item := attachment.Attachment{Path: path, ContentType: "image/png", Size: 3}
	transportCalls := 0
	uploader := New(roundTripFunc(func(request *http.Request) (*http.Response, error) {
		transportCalls++
		return nil, nil
	}))
	for _, rawURL := range []string{
		"http://upload.example.com/object",
		"https://user:pass@upload.example.com/object",
		"https://upload.example.com:444/object",
		"https://127.0.0.1/object",
		"https://10.0.0.1/object",
	} {
		if err := uploader.Put(context.Background(), rawURL, "p-key", item); err == nil {
			t.Fatalf("unsafe upload URL accepted: %s", rawURL)
		}
	}
	if transportCalls != 0 {
		t.Fatalf("transport calls = %d", transportCalls)
	}
}

func TestPutRevalidatesFileBeforeUpload(t *testing.T) {
	directory := t.TempDir()
	path := filepath.Join(directory, "cat.png")
	if err := os.WriteFile(path, []byte("changed"), 0o600); err != nil {
		t.Fatal(err)
	}
	uploader := New(roundTripFunc(func(request *http.Request) (*http.Response, error) {
		t.Fatal("transport must not be called")
		return nil, nil
	}))
	item := attachment.Attachment{Path: path, ContentType: "image/png", Size: 3}
	if err := uploader.Put(context.Background(), "https://upload.example.com/object", "p-key", item); err == nil {
		t.Fatal("changed file size was accepted")
	}

	target := filepath.Join(directory, "target.png")
	if err := os.WriteFile(target, []byte("png"), 0o600); err != nil {
		t.Fatal(err)
	}
	symlink := filepath.Join(directory, "linked.png")
	if err := os.Symlink(target, symlink); err != nil {
		t.Fatal(err)
	}
	item = attachment.Attachment{Path: symlink, ContentType: "image/png", Size: 3}
	if err := uploader.Put(context.Background(), "https://upload.example.com/object", "p-key", item); err == nil {
		t.Fatal("symlink was accepted")
	}
}

func TestPublicIPClassificationRejectsSSRFAddressRanges(t *testing.T) {
	tests := []struct {
		address string
		want    bool
	}{
		{"8.8.8.8", true},
		{"2606:4700:4700::1111", true},
		{"127.0.0.1", false},
		{"10.0.0.1", false},
		{"169.254.1.1", false},
		{"0.0.0.0", false},
		{"::1", false},
		{"fd00::1", false},
	}
	for _, testCase := range tests {
		if got := isPublicIP(net.ParseIP(testCase.address)); got != testCase.want {
			t.Fatalf("isPublicIP(%s) = %t", testCase.address, got)
		}
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (function roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}
