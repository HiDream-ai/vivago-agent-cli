package auth

import (
	"context"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestLoginFlowUsesRandomLoopbackCallbackAndStoresCredentials(t *testing.T) {
	store := &memoryCredentialStore{}
	opened := make(chan string, 1)
	flow := NewLoginFlow(store, func(_ context.Context, loginURL string) error {
		opened <- loginURL
		parsed, err := url.Parse(loginURL)
		if err != nil {
			return err
		}
		form := url.Values{
			"ticket":        {"test-ticket"},
			"refresh_token": {"test-refresh-token"},
			"state":         {parsed.Query().Get("state")},
		}
		go func() {
			_, _ = http.PostForm(
				"http://127.0.0.1:"+parsed.Query().Get("callback_port")+"/callback",
				form,
			)
		}()
		return nil
	}, LoginFlowOptions{Timeout: time.Second})

	result, err := flow.Login(context.Background(), "https://dev.vivago.ai/agent/login")
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	if result.Backend != "memory" {
		t.Fatalf("backend = %q", result.Backend)
	}
	loginURL := <-opened
	if strings.Contains(loginURL, "test-ticket") || strings.Contains(loginURL, "test-refresh-token") {
		t.Fatalf("login URL contains credentials: %s", loginURL)
	}
	if store.credentials.Ticket != "test-ticket" || store.credentials.RefreshToken != "test-refresh-token" {
		t.Fatalf("stored credentials = %#v", store.credentials)
	}
}

func TestLoginFlowReturnsManualURLWhenBrowserCannotOpen(t *testing.T) {
	store := &memoryCredentialStore{}
	manualURL := make(chan string, 1)
	flow := NewLoginFlow(store, func(context.Context, string) error {
		return errBrowserUnavailable
	}, LoginFlowOptions{
		Timeout: time.Second,
		OnManualURL: func(loginURL string) {
			manualURL <- loginURL
			parsed, _ := url.Parse(loginURL)
			form := url.Values{
				"ticket":        {"test-ticket"},
				"refresh_token": {"test-refresh-token"},
				"state":         {parsed.Query().Get("state")},
			}
			go func() {
				_, _ = http.PostForm(
					"http://127.0.0.1:"+parsed.Query().Get("callback_port")+"/callback",
					form,
				)
			}()
		},
	})

	if _, err := flow.Login(context.Background(), "https://dev.vivago.ai/agent/login"); err != nil {
		t.Fatalf("login: %v", err)
	}
	if got := <-manualURL; !strings.HasPrefix(got, "https://dev.vivago.ai/agent/login?") {
		t.Fatalf("manual URL = %q", got)
	}
}

func TestLoginFlowHoldsProcessLockThroughCallbackAndSave(t *testing.T) {
	store := &memoryCredentialStore{}
	processLock := &recordingProcessLock{}
	flow := NewLoginFlow(store, func(_ context.Context, loginURL string) error {
		if !processLock.held {
			t.Fatal("login browser opened without process lock")
		}
		parsed, _ := url.Parse(loginURL)
		form := url.Values{
			"ticket":        {"test-ticket"},
			"refresh_token": {"test-refresh-token"},
			"state":         {parsed.Query().Get("state")},
		}
		go func() {
			_, _ = http.PostForm(
				"http://127.0.0.1:"+parsed.Query().Get("callback_port")+"/callback",
				form,
			)
		}()
		return nil
	}, LoginFlowOptions{
		Timeout: time.Second,
		Lock:    processLock,
	})

	if _, err := flow.Login(context.Background(), "https://dev.vivago.ai/agent/login"); err != nil {
		t.Fatalf("login: %v", err)
	}
	if processLock.calls != 1 || processLock.held {
		t.Fatalf("lock state = calls %d, held %v", processLock.calls, processLock.held)
	}
}

var errBrowserUnavailable = &loginFlowTestError{"browser unavailable"}

type loginFlowTestError struct{ message string }

func (err *loginFlowTestError) Error() string { return err.message }

type recordingProcessLock struct {
	calls int
	held  bool
}

func (lock *recordingProcessLock) WithLock(_ context.Context, operation func() error) error {
	lock.calls++
	lock.held = true
	defer func() { lock.held = false }()
	return operation()
}
