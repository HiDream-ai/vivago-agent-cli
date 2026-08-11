//go:build !prod

package config

import "testing"

func TestDefaultBuildUsesOverseasDevelopmentEndpoints(t *testing.T) {
	profile := Current()

	if profile.Name != "dev" {
		t.Fatalf("name = %q, want dev", profile.Name)
	}
	if profile.APIBaseURL != "https://dev.vivago.ai" {
		t.Fatalf("API base URL = %q", profile.APIBaseURL)
	}
	if profile.LoginURL != "https://dev.vivago.ai/agent/login" {
		t.Fatalf("login URL = %q", profile.LoginURL)
	}
	if profile.WebBaseURL != "https://dev.vivago.ai" {
		t.Fatalf("web base URL = %q", profile.WebBaseURL)
	}
}
