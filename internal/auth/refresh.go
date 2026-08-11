package auth

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

const maxRefreshResponseBytes = 1024 * 1024

type RefreshFailureKind string

const (
	RefreshFailureTransient RefreshFailureKind = "transient"
	RefreshFailureInvalid   RefreshFailureKind = "invalid"
	RefreshFailureProtocol  RefreshFailureKind = "protocol"
)

type RefreshError struct {
	Kind       RefreshFailureKind
	StatusCode int
	ServerCode int
}

func (err *RefreshError) Error() string {
	switch {
	case err.StatusCode != 0:
		return fmt.Sprintf("token refresh failed with HTTP %d", err.StatusCode)
	case err.ServerCode != 0:
		return fmt.Sprintf("token refresh failed with server code %d", err.ServerCode)
	default:
		return fmt.Sprintf("token refresh failed: %s", err.Kind)
	}
}

type HTTPTokenRefresher struct {
	baseURL    string
	httpClient *http.Client
	userAgent  string
}

func NewHTTPTokenRefresher(
	baseURL string,
	httpClient *http.Client,
	userAgent string,
) *HTTPTokenRefresher {
	return &HTTPTokenRefresher{
		baseURL:    strings.TrimRight(baseURL, "/"),
		httpClient: httpClient,
		userAgent:  userAgent,
	}
}

func (refresher *HTTPTokenRefresher) Refresh(ctx context.Context, refreshToken string) (string, error) {
	if strings.TrimSpace(refreshToken) == "" {
		return "", fmt.Errorf("refresh token is required")
	}
	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		refresher.baseURL+"/prod-api/user/apikey2token",
		nil,
	)
	if err != nil {
		return "", fmt.Errorf("create refresh request: %w", err)
	}
	request.Header.Set("Refresh-Token", refreshToken)
	request.Header.Set("Accept", "application/json")
	request.Header.Set("User-Agent", refresher.userAgent)

	response, err := refresher.httpClient.Do(request)
	if err != nil {
		return "", &RefreshError{Kind: RefreshFailureTransient}
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		kind := RefreshFailureProtocol
		if response.StatusCode == http.StatusBadRequest ||
			response.StatusCode == http.StatusUnauthorized ||
			response.StatusCode == http.StatusForbidden {
			kind = RefreshFailureInvalid
		} else if response.StatusCode == http.StatusRequestTimeout ||
			response.StatusCode == http.StatusTooManyRequests ||
			response.StatusCode >= 500 {
			kind = RefreshFailureTransient
		}
		return "", &RefreshError{Kind: kind, StatusCode: response.StatusCode}
	}
	var payload struct {
		Code   int `json:"code"`
		Result struct {
			Token string `json:"token"`
		} `json:"result"`
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, maxRefreshResponseBytes)).Decode(&payload); err != nil {
		return "", &RefreshError{Kind: RefreshFailureProtocol}
	}
	if payload.Code != 0 {
		return "", &RefreshError{Kind: RefreshFailureInvalid, ServerCode: payload.Code}
	}
	if strings.TrimSpace(payload.Result.Token) == "" {
		return "", &RefreshError{Kind: RefreshFailureProtocol}
	}
	return payload.Result.Token, nil
}
