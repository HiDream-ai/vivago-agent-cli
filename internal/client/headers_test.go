package client

import "testing"

func TestRequestHeadersKeepWebPlatformAndMarkCLISource(t *testing.T) {
	headers := RequestHeaders("test-ticket", Metadata{
		Version: "0.3.0-dev",
		OS:      "darwin",
		Arch:    "arm64",
		Host:    "codex",
	})

	want := map[string]string{
		"Authorization":     "Bearer test-ticket",
		"Content-Type":      "application/json",
		"X-Source":          "cli",
		"X-Client-Platform": "web",
		"X-Client-Version":  "0.3.0-dev",
		"User-Agent":        "vivago-agent-cli/0.3.0-dev (darwin; arm64; codex)",
	}
	for name, value := range want {
		if headers.Get(name) != value {
			t.Errorf("%s = %q, want %q", name, headers.Get(name), value)
		}
	}
}
