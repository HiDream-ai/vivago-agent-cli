package auth

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestCallbackAcceptsValidFormOnceWithoutEchoingCredentials(t *testing.T) {
	handler := NewCallbackHandler("expected-state")
	form := url.Values{
		"ticket":        {"secret-ticket"},
		"refresh_token": {"secret-refresh"},
		"state":         {"expected-state"},
	}
	request := httptest.NewRequest(
		http.MethodPost,
		"http://127.0.0.1:54321/callback",
		strings.NewReader(form.Encode()),
	)
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	request.RemoteAddr = "127.0.0.1:12345"
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if strings.Contains(response.Body.String(), "secret-ticket") ||
		strings.Contains(response.Body.String(), "secret-refresh") {
		t.Fatalf("response body contains credentials: %q", response.Body.String())
	}
	select {
	case result := <-handler.Result():
		if result.Ticket != "secret-ticket" || result.RefreshToken != "secret-refresh" {
			t.Fatalf("result = %#v", result)
		}
	case <-time.After(time.Second):
		t.Fatal("callback result was not delivered")
	}
}

func TestCallbackRejectsNonLoopbackPeer(t *testing.T) {
	handler := NewCallbackHandler("expected-state")
	form := url.Values{
		"ticket":        {"secret-ticket"},
		"refresh_token": {"secret-refresh"},
		"state":         {"expected-state"},
	}
	request := httptest.NewRequest(
		http.MethodPost,
		"http://127.0.0.1:54321/callback",
		strings.NewReader(form.Encode()),
	)
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	request.RemoteAddr = "203.0.113.10:12345"
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403", response.Code)
	}
	select {
	case result := <-handler.Result():
		t.Fatalf("unexpected callback result: %#v", result)
	default:
	}
}

func TestCallbackWritesSuccessPageBeforeDeliveringCredentials(t *testing.T) {
	handler := NewCallbackHandler("expected-state")
	form := url.Values{
		"ticket":        {"secret-ticket"},
		"refresh_token": {"secret-refresh"},
		"state":         {"expected-state"},
	}
	request := httptest.NewRequest(
		http.MethodPost,
		"http://127.0.0.1:54321/callback",
		strings.NewReader(form.Encode()),
	)
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	request.RemoteAddr = "127.0.0.1:12345"
	writer := newBlockingResponseWriter()

	done := make(chan struct{})
	go func() {
		handler.ServeHTTP(writer, request)
		close(done)
	}()

	select {
	case <-handler.Result():
		t.Fatal("credentials were delivered before writing the success page")
	case <-writer.writeStarted:
	}
	select {
	case <-handler.Result():
		t.Fatal("credentials were delivered before the success page write completed")
	default:
	}
	close(writer.allowWrite)
	select {
	case <-handler.Result():
	case <-time.After(time.Second):
		t.Fatal("credentials were not delivered after writing the success page")
	}
	<-done
}

type blockingResponseWriter struct {
	header       http.Header
	writeStarted chan struct{}
	allowWrite   chan struct{}
	once         sync.Once
}

func newBlockingResponseWriter() *blockingResponseWriter {
	return &blockingResponseWriter{
		header:       make(http.Header),
		writeStarted: make(chan struct{}),
		allowWrite:   make(chan struct{}),
	}
}

func (writer *blockingResponseWriter) Header() http.Header {
	return writer.header
}

func (*blockingResponseWriter) WriteHeader(int) {}

func (writer *blockingResponseWriter) Write(payload []byte) (int, error) {
	writer.once.Do(func() { close(writer.writeStarted) })
	<-writer.allowWrite
	return len(payload), nil
}
