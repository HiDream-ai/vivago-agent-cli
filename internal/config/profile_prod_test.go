//go:build prod

package config

import "testing"

func TestProductionBuildUsesOnlyOverseasProductionEndpoints(t *testing.T) {
	profile := Current()

	if profile.Name != "prod" {
		t.Fatalf("name = %q, want prod", profile.Name)
	}
	if profile.APIBaseURL != "https://vivago.ai" {
		t.Fatalf("API base URL = %q", profile.APIBaseURL)
	}
	if profile.LoginURL != "https://vivago.ai/agent/login" {
		t.Fatalf("login URL = %q", profile.LoginURL)
	}
	if profile.WebBaseURL != "https://vivago.ai" {
		t.Fatalf("web base URL = %q", profile.WebBaseURL)
	}
}
