package auth

import (
	"context"
	"testing"
)

func TestCommandRuntimeDelegatesStatusAndLogout(t *testing.T) {
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       "malformed-ticket",
		RefreshToken: "test-refresh-token",
	}}
	runtime := NewCommandRuntime(
		store,
		"https://dev.vivago.ai/agent/login",
		nil,
		CommandRuntimeOptions{},
	)

	status, err := runtime.Status(context.Background())
	if err != nil {
		t.Fatalf("status: %v", err)
	}
	if !status.LoggedIn || !status.NeedsRefresh || status.Backend != "memory" {
		t.Fatalf("status = %#v", status)
	}
	if err := runtime.Logout(context.Background()); err != nil {
		t.Fatalf("logout: %v", err)
	}
	if !store.deleted {
		t.Fatal("runtime did not delete local credentials")
	}
}

func TestCommandRuntimeRefreshReturnsOnlySafeCompletionMetadata(t *testing.T) {
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       "old-ticket",
		RefreshToken: "test-refresh-token",
	}}
	refreshCalls := 0
	runtime := NewCommandRuntime(
		store,
		"https://dev.vivago.ai/agent/login",
		nil,
		CommandRuntimeOptions{
			Refresher: credentialRefresherFunc(func(context.Context) error {
				refreshCalls++
				return nil
			}),
		},
	)

	result, err := runtime.Refresh(context.Background())
	if err != nil {
		t.Fatalf("refresh: %v", err)
	}
	if refreshCalls != 1 {
		t.Fatalf("refresh calls = %d, want 1", refreshCalls)
	}
	if !result.Refreshed || result.Backend != "memory" {
		t.Fatalf("result = %#v", result)
	}
}

type credentialRefresherFunc func(context.Context) error

func (function credentialRefresherFunc) Refresh(ctx context.Context) error {
	return function(ctx)
}
