package auth

import (
	"errors"
	"path/filepath"
	"testing"
)

func TestFileCredentialFallbackIsAllowedOnlyOnLinux(t *testing.T) {
	tests := []struct {
		platform string
		want     bool
	}{
		{platform: "linux", want: true},
		{platform: "darwin", want: false},
		{platform: "windows", want: false},
	}
	for _, testCase := range tests {
		t.Run(testCase.platform, func(t *testing.T) {
			if got := FileFallbackAllowed(testCase.platform); got != testCase.want {
				t.Fatalf("FileFallbackAllowed(%q) = %v, want %v", testCase.platform, got, testCase.want)
			}
		})
	}
}

func TestSelectCredentialStoreFallsBackToFileOnlyOnLinux(t *testing.T) {
	profile := CredentialProfile{FilePath: "/tmp/config/vivago-agent/credentials-dev.json"}
	backendError := errors.New("system backend unavailable")

	store, err := SelectCredentialStore("linux", profile, nil, backendError)
	if err != nil {
		t.Fatalf("linux store: %v", err)
	}
	if store.Backend() != "file" {
		t.Fatalf("linux backend = %q, want file", store.Backend())
	}

	for _, platform := range []string{"darwin", "windows"} {
		t.Run(platform, func(t *testing.T) {
			store, err := SelectCredentialStore(platform, profile, nil, backendError)
			if err == nil {
				t.Fatalf("store = %#v, want system credential dependency error", store)
			}
		})
	}
}

func TestSelectCredentialStoreUsesPlatformSystemBackend(t *testing.T) {
	profile := CredentialProfile{Service: "test-service", Account: "test-account"}
	for _, testCase := range []struct {
		platform string
		backend  string
	}{
		{platform: "darwin", backend: "keychain"},
		{platform: "windows", backend: "credential-manager"},
		{platform: "linux", backend: "secret-service"},
	} {
		t.Run(testCase.platform, func(t *testing.T) {
			store, err := SelectCredentialStore(testCase.platform, profile, &memorySystemKeyring{}, nil)
			if err != nil {
				t.Fatalf("select store: %v", err)
			}
			if store.Backend() != testCase.backend {
				t.Fatalf("backend = %q, want %q", store.Backend(), testCase.backend)
			}
		})
	}
}

func TestCredentialProfileSeparatesDevelopmentAndProduction(t *testing.T) {
	tests := []struct {
		buildProfile string
		service      string
		account      string
		filename     string
		lockFilename string
	}{
		{
			buildProfile: "dev",
			service:      "ai.hidream.vivago-agent.dev",
			account:      "overseas-dev",
			filename:     "credentials-dev.json",
			lockFilename: "auth-dev.lock",
		},
		{
			buildProfile: "prod",
			service:      "ai.hidream.vivago-agent",
			account:      "overseas-prod",
			filename:     "credentials-prod.json",
			lockFilename: "auth-prod.lock",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.buildProfile, func(t *testing.T) {
			profile, err := ResolveCredentialProfile(testCase.buildProfile, "/tmp/config")
			if err != nil {
				t.Fatalf("resolve profile: %v", err)
			}
			if profile.Service != testCase.service || profile.Account != testCase.account {
				t.Fatalf("profile = %#v", profile)
			}
			if profile.FilePath != filepath.Join("/tmp/config", "vivago-agent", testCase.filename) {
				t.Fatalf("file path = %q", profile.FilePath)
			}
			if profile.LockPath != filepath.Join("/tmp/config", "vivago-agent", testCase.lockFilename) {
				t.Fatalf("lock path = %q", profile.LockPath)
			}
		})
	}
}
