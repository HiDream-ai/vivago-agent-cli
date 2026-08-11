package auth

import (
	"encoding/base64"
	"net/url"
	"testing"
)

func TestBuildLoginURLUsesFixedClientAndCallbackParameters(t *testing.T) {
	state := "one-time_state-1234567890abcdefgh"
	loginURL, err := BuildLoginURL(
		"https://dev.vivago.ai/agent/login",
		54321,
		state,
	)
	if err != nil {
		t.Fatalf("build login URL: %v", err)
	}

	parsed, err := url.Parse(loginURL)
	if err != nil {
		t.Fatalf("parse login URL: %v", err)
	}
	if parsed.Scheme != "https" || parsed.Host != "dev.vivago.ai" || parsed.Path != "/agent/login" {
		t.Fatalf("login URL = %q", loginURL)
	}
	query := parsed.Query()
	if query.Get("client") != "vivago-agent-cli" {
		t.Fatalf("client = %q", query.Get("client"))
	}
	if query.Get("callback_port") != "54321" {
		t.Fatalf("callback_port = %q", query.Get("callback_port"))
	}
	if query.Get("state") != state {
		t.Fatalf("state = %q", query.Get("state"))
	}
	if len(query) != 3 {
		t.Fatalf("query = %#v, want exactly three fields", query)
	}
}

func TestGenerateStateUsesThirtyTwoRandomBytesAndURLSafeEncoding(t *testing.T) {
	state, err := GenerateState()
	if err != nil {
		t.Fatalf("generate state: %v", err)
	}
	decoded, err := base64.RawURLEncoding.DecodeString(state)
	if err != nil {
		t.Fatalf("state is not unpadded base64url: %v", err)
	}
	if len(decoded) != 32 {
		t.Fatalf("decoded state length = %d, want 32", len(decoded))
	}
}
