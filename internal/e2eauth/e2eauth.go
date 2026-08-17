package e2eauth

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
)

const DisabledRefreshToken = "ci-ticket-only-refresh-disabled"

var ErrCredentialNotUsable = errors.New("one-time credential is missing, invalid, or expires too soon")

type SeedOptions struct {
	Profile         string
	Ticket          string
	Platform        string
	ConfigDirectory string
	SystemKeyring   auth.SystemKeyring
	Now             time.Time
	MinimumValidity time.Duration
}

type LoadOptions struct {
	Profile         string
	Platform        string
	ConfigDirectory string
	SystemKeyring   auth.SystemKeyring
	Now             time.Time
	MinimumValidity time.Duration
}

func Seed(ctx context.Context, options SeedOptions) (string, error) {
	if err := validateTicket(options.Ticket, normalizedNow(options.Now), options.MinimumValidity); err != nil {
		return "", err
	}
	store, err := credentialStore(
		ctx,
		options.Profile,
		options.Platform,
		options.ConfigDirectory,
		options.SystemKeyring,
	)
	if err != nil {
		return "", err
	}
	if err := store.Save(ctx, auth.Credentials{
		Ticket:       strings.TrimSpace(options.Ticket),
		RefreshToken: DisabledRefreshToken,
	}); err != nil {
		return "", fmt.Errorf("seed one-time credential: %w", err)
	}
	return store.Backend(), nil
}

func LoadFreshTicket(ctx context.Context, options LoadOptions) (string, string, error) {
	store, err := credentialStore(
		ctx,
		options.Profile,
		options.Platform,
		options.ConfigDirectory,
		options.SystemKeyring,
	)
	if err != nil {
		return "", "", err
	}
	credentials, err := store.Load(ctx)
	if err != nil {
		return "", "", fmt.Errorf("load local credential: %w", err)
	}
	if err := validateTicket(
		credentials.Ticket,
		normalizedNow(options.Now),
		options.MinimumValidity,
	); err != nil {
		return "", "", err
	}
	return credentials.Ticket, store.Backend(), nil
}

func Clear(
	ctx context.Context,
	profile string,
	platform string,
	configDirectory string,
	systemKeyring auth.SystemKeyring,
) (string, error) {
	store, err := credentialStore(ctx, profile, platform, configDirectory, systemKeyring)
	if err != nil {
		return "", err
	}
	if err := store.Delete(ctx); err != nil {
		return "", fmt.Errorf("clear one-time credential: %w", err)
	}
	return store.Backend(), nil
}

func validateTicket(ticket string, now time.Time, minimumValidity time.Duration) error {
	if minimumValidity <= 0 {
		return ErrCredentialNotUsable
	}
	parts := strings.Split(strings.TrimSpace(ticket), ".")
	if len(parts) != 3 {
		return ErrCredentialNotUsable
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return ErrCredentialNotUsable
	}
	var claims struct {
		ExpiresAt int64 `json:"exp"`
	}
	if err := json.Unmarshal(payload, &claims); err != nil || claims.ExpiresAt <= 0 {
		return ErrCredentialNotUsable
	}
	if !time.Unix(claims.ExpiresAt, 0).After(now.Add(minimumValidity)) {
		return ErrCredentialNotUsable
	}
	return nil
}

func credentialStore(
	ctx context.Context,
	buildProfile string,
	platform string,
	configDirectory string,
	systemKeyring auth.SystemKeyring,
) (auth.CredentialStore, error) {
	profile, err := auth.ResolveCredentialProfile(buildProfile, configDirectory)
	if err != nil {
		return nil, err
	}
	probeError := errors.New("system credential store is unavailable")
	if systemKeyring != nil {
		probeError = auth.ProbeSystemKeyring(ctx, systemKeyring, profile)
	}
	store, err := auth.SelectCredentialStore(platform, profile, systemKeyring, probeError)
	if err != nil {
		return nil, fmt.Errorf("select one-time credential store: %w", err)
	}
	return store, nil
}

func normalizedNow(now time.Time) time.Time {
	if now.IsZero() {
		return time.Now()
	}
	return now
}
