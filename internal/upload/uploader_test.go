package upload

import (
	"context"
	"io"
	"net"
	"net/http"
	"net/url"
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

func TestSecureHTTPClientUsesConfiguredLocalEnvironmentProxy(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	t.Setenv("HTTPS_PROXY", "http://"+listener.Addr().String())
	t.Setenv("https_proxy", "")
	t.Setenv("NO_PROXY", "")
	t.Setenv("no_proxy", "")

	client := newSecureHTTPClient(staticResolver{addresses: []net.IPAddr{{IP: net.ParseIP("8.8.8.8")}}})
	selector, ok := client.Transport.(requestTransportSelector)
	if !ok {
		t.Fatalf("transport %T does not separate direct and proxy routes", client.Transport)
	}
	request, err := http.NewRequest(http.MethodPut, "https://upload.example.com/object", nil)
	if err != nil {
		t.Fatal(err)
	}
	selected, err := selector.transportFor(request)
	if err != nil {
		t.Fatalf("select transport: %v", err)
	}
	transport, ok := selected.(*http.Transport)
	if !ok {
		t.Fatalf("selected transport = %T", selected)
	}
	if transport.Proxy == nil {
		t.Fatal("environment proxy selector is disabled")
	}
	proxyURL, err := transport.Proxy(request)
	if err != nil {
		t.Fatalf("select proxy: %v", err)
	}
	if proxyURL == nil || proxyURL.Host != listener.Addr().String() {
		t.Fatalf("proxy = %v", proxyURL)
	}
	connection, err := transport.DialContext(context.Background(), "tcp", proxyURL.Host)
	if err != nil {
		t.Fatalf("dial configured local proxy: %v", err)
	}
	connection.Close()
}

func TestEnvironmentProxyRouteRejectsPrivateUploadTarget(t *testing.T) {
	proxyURL, err := url.Parse("http://127.0.0.1:7890")
	if err != nil {
		t.Fatal(err)
	}
	transport := &environmentProxyTransport{
		proxy:   func(*http.Request) (*url.URL, error) { return proxyURL, nil },
		direct:  &http.Transport{},
		proxied: &http.Transport{},
		resolver: staticResolver{addresses: []net.IPAddr{{
			IP: net.ParseIP("10.0.0.9"),
		}}},
	}
	request, err := http.NewRequest(http.MethodPut, "https://upload.example.com/object", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := transport.transportFor(request); err == nil {
		t.Fatal("private upload target was routed through the proxy")
	}
}

func TestNoEnvironmentProxyKeepsSecureDirectUploadTransport(t *testing.T) {
	direct := &http.Transport{}
	transport := &environmentProxyTransport{
		proxy:   func(*http.Request) (*url.URL, error) { return nil, nil },
		direct:  direct,
		proxied: &http.Transport{},
	}
	request, err := http.NewRequest(http.MethodPut, "https://upload.example.com/object", nil)
	if err != nil {
		t.Fatal(err)
	}
	selected, err := transport.transportFor(request)
	if err != nil {
		t.Fatalf("select direct transport: %v", err)
	}
	if selected != direct {
		t.Fatalf("selected transport = %T, want direct transport", selected)
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

type requestTransportSelector interface {
	transportFor(*http.Request) (http.RoundTripper, error)
}

type staticResolver struct {
	addresses []net.IPAddr
}

func (resolver staticResolver) LookupIPAddr(context.Context, string) ([]net.IPAddr, error) {
	return resolver.addresses, nil
}

func (function roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}
