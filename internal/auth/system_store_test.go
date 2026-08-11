package auth

import (
	"context"
	"testing"
)

type memorySystemKeyring struct {
	service string
	account string
	secret  string
}

func (keyring *memorySystemKeyring) Get(context.Context, string, string) (string, error) {
	return keyring.secret, nil
}

func (keyring *memorySystemKeyring) Set(_ context.Context, service, account, secret string) error {
	keyring.service = service
	keyring.account = account
	keyring.secret = secret
	return nil
}

func (keyring *memorySystemKeyring) Delete(context.Context, string, string) error {
	keyring.secret = ""
	return nil
}

func TestSystemCredentialStoreKeepsCredentialsBehindKeyringBoundary(t *testing.T) {
	keyring := &memorySystemKeyring{}
	store := NewSystemCredentialStore(
		"keychain",
		CredentialProfile{
			Service: "ai.hidream.vivago-agent.dev",
			Account: "overseas-dev",
		},
		keyring,
	)
	want := Credentials{Ticket: "test-ticket", RefreshToken: "test-refresh-token"}

	if err := store.Save(context.Background(), want); err != nil {
		t.Fatalf("save credentials: %v", err)
	}
	if keyring.service != "ai.hidream.vivago-agent.dev" || keyring.account != "overseas-dev" {
		t.Fatalf("keyring identity = %q / %q", keyring.service, keyring.account)
	}
	if keyring.secret == "" {
		t.Fatal("keyring received no secret")
	}
	got, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load credentials: %v", err)
	}
	if got != want {
		t.Fatalf("credentials = %#v, want %#v", got, want)
	}
	if store.Backend() != "keychain" {
		t.Fatalf("backend = %q", store.Backend())
	}
}
