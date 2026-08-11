package artifact

import (
	"bytes"
	"context"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type staticResolver struct {
	addresses []net.IPAddr
	err       error
}

func (resolver staticResolver) LookupIPAddr(context.Context, string) ([]net.IPAddr, error) {
	return resolver.addresses, resolver.err
}

func TestResolvePublicAddressesRejectsPrivateAndMixedDNSAnswers(t *testing.T) {
	tests := []struct {
		name      string
		addresses []string
		wantOK    bool
	}{
		{name: "public IPv4", addresses: []string{"8.8.8.8"}, wantOK: true},
		{name: "public IPv6", addresses: []string{"2606:4700:4700::1111"}, wantOK: true},
		{name: "loopback", addresses: []string{"127.0.0.1"}},
		{name: "private IPv4", addresses: []string{"10.0.0.1"}},
		{name: "link local", addresses: []string{"169.254.1.1"}},
		{name: "private IPv6", addresses: []string{"fd00::1"}},
		{name: "mixed", addresses: []string{"8.8.8.8", "127.0.0.1"}},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			addresses := make([]net.IPAddr, 0, len(testCase.addresses))
			for _, raw := range testCase.addresses {
				addresses = append(addresses, net.IPAddr{IP: net.ParseIP(raw)})
			}
			resolved, err := resolvePublicAddresses(
				context.Background(),
				staticResolver{addresses: addresses},
				"storage.vivago.ai",
			)
			if testCase.wantOK {
				if err != nil || len(resolved) != len(addresses) {
					t.Fatalf("resolved = %#v, err = %v", resolved, err)
				}
				return
			}
			if err == nil {
				t.Fatalf("unsafe addresses accepted: %#v", resolved)
			}
		})
	}
}

func TestDownloadStreamsToAbsolutePathWithoutOverwrite(t *testing.T) {
	directory := t.TempDir()
	destination := filepath.Join(directory, "cat.jpg")
	downloader := NewDownloader(roundTripFunc(func(request *http.Request) (*http.Response, error) {
		return downloadResponse(request, "image/jpeg", []byte("valid-image-bytes")), nil
	}))

	result, err := downloader.Download(
		context.Background(), "image", "p-cat", destination,
	)
	if err != nil {
		t.Fatalf("download: %v", err)
	}
	if result.Path != destination || result.Bytes != int64(len("valid-image-bytes")) || result.ContentType != "image/jpeg" {
		t.Fatalf("result = %#v", result)
	}
	content, err := os.ReadFile(destination)
	if err != nil || string(content) != "valid-image-bytes" {
		t.Fatalf("content = %q, err = %v", content, err)
	}

	if _, err := downloader.Download(context.Background(), "image", "p-cat", destination); err == nil {
		t.Fatal("existing destination was overwritten")
	}
	content, _ = os.ReadFile(destination)
	if string(content) != "valid-image-bytes" {
		t.Fatalf("existing content changed: %q", content)
	}
}

func TestDownloadRejectsWrongContentTypeAndOversizedBodyWithoutPartialFile(t *testing.T) {
	tests := []struct {
		name        string
		contentType string
		body        []byte
		maxBytes    int64
	}{
		{name: "wrong type", contentType: "text/html", body: []byte("not an image")},
		{name: "too large", contentType: "image/png", body: bytes.Repeat([]byte("x"), 9), maxBytes: 8},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			destination := filepath.Join(t.TempDir(), "cat.png")
			downloader := NewDownloader(roundTripFunc(func(request *http.Request) (*http.Response, error) {
				return downloadResponse(request, testCase.contentType, testCase.body), nil
			}))
			if testCase.maxBytes != 0 {
				downloader.limits["image"] = testCase.maxBytes
			}
			if _, err := downloader.Download(context.Background(), "image", "p-cat", destination); err == nil {
				t.Fatal("unsafe download succeeded")
			}
			if _, err := os.Stat(destination); !os.IsNotExist(err) {
				t.Fatalf("partial destination exists: %v", err)
			}
			entries, err := os.ReadDir(filepath.Dir(destination))
			if err != nil || len(entries) != 0 {
				t.Fatalf("temporary files remain: %#v, err = %v", entries, err)
			}
		})
	}
}

func TestRedirectPolicyRejectsCrossHostAndInsecureRedirects(t *testing.T) {
	policy := secureRedirectPolicy()
	original, _ := http.NewRequest(http.MethodGet, "https://storage.vivago.ai/image/cat.jpg", nil)
	for _, target := range []string{
		"http://storage.vivago.ai/image/cat.jpg",
		"https://media.vivago.ai/cat.jpg",
		"https://evil.test/cat.jpg",
	} {
		request, _ := http.NewRequest(http.MethodGet, target, nil)
		if err := policy(request, []*http.Request{original}); err == nil {
			t.Fatalf("redirect accepted: %s", target)
		}
	}
	sameHost, _ := http.NewRequest(http.MethodGet, "https://storage.vivago.ai/image/cat-v2.jpg", nil)
	if err := policy(sameHost, []*http.Request{original}); err != nil {
		t.Fatalf("same-host HTTPS redirect rejected: %v", err)
	}
}

func TestPreviewUsesSafeExtensionAndUniqueTemporaryDirectory(t *testing.T) {
	downloader := NewDownloader(roundTripFunc(func(request *http.Request) (*http.Response, error) {
		return downloadResponse(request, "image/png", []byte("png-bytes")), nil
	}))

	result, err := downloader.Preview(
		context.Background(),
		"image",
		"https://storage.vivago.ai/image/generated.png?download=1",
	)
	if err != nil {
		t.Fatalf("preview: %v", err)
	}
	defer os.RemoveAll(filepath.Dir(result.Path))
	if !filepath.IsAbs(result.Path) || filepath.Ext(result.Path) != ".png" {
		t.Fatalf("preview path = %q", result.Path)
	}
	if !strings.HasPrefix(filepath.Base(filepath.Dir(result.Path)), "vivago-agent-preview-") {
		t.Fatalf("preview directory = %q", filepath.Dir(result.Path))
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (function roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}

func downloadResponse(request *http.Request, contentType string, body []byte) *http.Response {
	return &http.Response{
		StatusCode:    http.StatusOK,
		Header:        http.Header{"Content-Type": []string{contentType}},
		Body:          io.NopCloser(strings.NewReader(string(body))),
		ContentLength: int64(len(body)),
		Request:       request,
	}
}
