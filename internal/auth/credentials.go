package auth

import (
	"context"
	"errors"
	"fmt"
	"path/filepath"
	"strings"
)

var ErrCredentialsNotFound = errors.New("credentials not found")

type Credentials struct {
	Ticket       string `json:"ticket"`
	RefreshToken string `json:"refresh_token"`
}

type CredentialProfile struct {
	Service  string
	Account  string
	FilePath string
	LockPath string
}

type CredentialStore interface {
	Load(context.Context) (Credentials, error)
	Save(context.Context, Credentials) error
	Delete(context.Context) error
	Backend() string
}

func FileFallbackAllowed(platform string) bool {
	return platform == "linux"
}

func SelectCredentialStore(
	platform string,
	profile CredentialProfile,
	systemKeyring SystemKeyring,
	systemError error,
) (CredentialStore, error) {
	backend, err := systemBackendName(platform)
	if err != nil {
		return nil, err
	}
	if systemKeyring != nil && systemError == nil {
		return NewSystemCredentialStore(backend, profile, systemKeyring), nil
	}
	if FileFallbackAllowed(platform) {
		return NewFileCredentialStore(profile.FilePath), nil
	}
	if systemError == nil {
		systemError = fmt.Errorf("backend did not initialize")
	}
	return nil, fmt.Errorf("%s credential store is unavailable: %w", backend, systemError)
}

func systemBackendName(platform string) (string, error) {
	switch platform {
	case "darwin":
		return "keychain", nil
	case "windows":
		return "credential-manager", nil
	case "linux":
		return "secret-service", nil
	default:
		return "", fmt.Errorf("unsupported credential platform %q", platform)
	}
}

func ResolveCredentialProfile(buildProfile, configDirectory string) (CredentialProfile, error) {
	if strings.TrimSpace(configDirectory) == "" {
		return CredentialProfile{}, fmt.Errorf("config directory is required")
	}
	switch buildProfile {
	case "dev":
		return CredentialProfile{
			Service:  "ai.hidream.vivago-agent.dev",
			Account:  "overseas-dev",
			FilePath: filepath.Join(configDirectory, "vivago-agent", "credentials-dev.json"),
			LockPath: filepath.Join(configDirectory, "vivago-agent", "auth-dev.lock"),
		}, nil
	case "prod":
		return CredentialProfile{
			Service:  "ai.hidream.vivago-agent",
			Account:  "overseas-prod",
			FilePath: filepath.Join(configDirectory, "vivago-agent", "credentials-prod.json"),
			LockPath: filepath.Join(configDirectory, "vivago-agent", "auth-prod.lock"),
		}, nil
	default:
		return CredentialProfile{}, fmt.Errorf("unsupported build profile %q", buildProfile)
	}
}
