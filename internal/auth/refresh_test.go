package auth

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"
)

type authRoundTripFunc func(*http.Request) (*http.Response, error)

func (function authRoundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}

func TestHTTPTokenRefresherClassifiesNetworkFailureWithoutLeakingToken(t *testing.T) {
	httpClient := &http.Client{Transport: authRoundTripFunc(func(*http.Request) (*http.Response, error) {
		return nil, fmt.Errorf("dial failed while sending test-refresh-token")
	})}
	refresher := NewHTTPTokenRefresher("https://dev.vivago.ai", httpClient, "vivago-agent-cli/dev")

	_, err := refresher.Refresh(context.Background(), "test-refresh-token")
	var refreshError *RefreshError
	if !errors.As(err, &refreshError) {
		t.Fatalf("error = %v, want RefreshError", err)
	}
	if refreshError.Kind != RefreshFailureTransient {
		t.Fatalf("failure kind = %q", refreshError.Kind)
	}
	if strings.Contains(err.Error(), "test-refresh-token") {
		t.Fatalf("error leaked refresh token: %v", err)
	}
}

func TestHTTPTokenRefresherClassifiesRejectedRefreshTokenAsInvalid(t *testing.T) {
	httpClient := &http.Client{Transport: authRoundTripFunc(func(request *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       io.NopCloser(strings.NewReader(`{"code":40101,"message":"invalid refresh token"}`)),
			Request:    request,
		}, nil
	})}
	refresher := NewHTTPTokenRefresher("https://dev.vivago.ai", httpClient, "vivago-agent-cli/dev")

	_, err := refresher.Refresh(context.Background(), "test-refresh-token")
	var refreshError *RefreshError
	if !errors.As(err, &refreshError) {
		t.Fatalf("error = %v, want RefreshError", err)
	}
	if refreshError.Kind != RefreshFailureInvalid || refreshError.ServerCode != 40101 {
		t.Fatalf("refresh error = %#v", refreshError)
	}
}

func TestHTTPTokenRefresherUsesExistingWebContract(t *testing.T) {
	httpClient := &http.Client{Transport: authRoundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.Method != http.MethodGet || request.URL.String() != "https://dev.vivago.ai/prod-api/user/apikey2token" {
			t.Errorf("request = %s %s", request.Method, request.URL.String())
		}
		if request.Header.Get("Refresh-Token") != "test-refresh-token" {
			t.Errorf("Refresh-Token header was not set")
		}
		if request.Header.Get("Accept") != "application/json" {
			t.Errorf("Accept = %q", request.Header.Get("Accept"))
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/json"}},
			Body:       io.NopCloser(strings.NewReader(`{"code":0,"result":{"token":"new-ticket"}}`)),
			Request:    request,
		}, nil
	})}
	refresher := NewHTTPTokenRefresher(
		"https://dev.vivago.ai",
		httpClient,
		"vivago-agent-cli/0.3.0-dev (darwin; arm64; codex)",
	)

	ticket, err := refresher.Refresh(context.Background(), "test-refresh-token")
	if err != nil {
		t.Fatalf("refresh token: %v", err)
	}
	if ticket != "new-ticket" {
		t.Fatalf("ticket = %q", ticket)
	}
}
