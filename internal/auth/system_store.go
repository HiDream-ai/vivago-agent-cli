package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

var ErrSystemKeyringItemNotFound = errors.New("system keyring item not found")

type SystemKeyring interface {
	Get(context.Context, string, string) (string, error)
	Set(context.Context, string, string, string) error
	Delete(context.Context, string, string) error
}

type SystemCredentialStore struct {
	backend string
	profile CredentialProfile
	keyring SystemKeyring
}

func NewSystemCredentialStore(
	backend string,
	profile CredentialProfile,
	keyring SystemKeyring,
) *SystemCredentialStore {
	return &SystemCredentialStore{
		backend: backend,
		profile: profile,
		keyring: keyring,
	}
}

func (store *SystemCredentialStore) Backend() string {
	return store.backend
}

func (store *SystemCredentialStore) Save(ctx context.Context, credentials Credentials) error {
	if strings.TrimSpace(credentials.Ticket) == "" || strings.TrimSpace(credentials.RefreshToken) == "" {
		return fmt.Errorf("ticket and refresh token are required")
	}
	payload, err := json.Marshal(credentials)
	if err != nil {
		return fmt.Errorf("encode credentials: %w", err)
	}
	if err := store.keyring.Set(ctx, store.profile.Service, store.profile.Account, string(payload)); err != nil {
		return fmt.Errorf("save credentials to %s: %w", store.backend, err)
	}
	return nil
}

func (store *SystemCredentialStore) Load(ctx context.Context) (Credentials, error) {
	payload, err := store.keyring.Get(ctx, store.profile.Service, store.profile.Account)
	if errors.Is(err, ErrSystemKeyringItemNotFound) {
		return Credentials{}, ErrCredentialsNotFound
	}
	if err != nil {
		return Credentials{}, fmt.Errorf("load credentials from %s: %w", store.backend, err)
	}
	var credentials Credentials
	if err := json.Unmarshal([]byte(payload), &credentials); err != nil {
		return Credentials{}, fmt.Errorf("decode credentials from %s: %w", store.backend, err)
	}
	if credentials.Ticket == "" || credentials.RefreshToken == "" {
		return Credentials{}, fmt.Errorf("credentials in %s are incomplete", store.backend)
	}
	return credentials, nil
}

func (store *SystemCredentialStore) Delete(ctx context.Context) error {
	err := store.keyring.Delete(ctx, store.profile.Service, store.profile.Account)
	if errors.Is(err, ErrSystemKeyringItemNotFound) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("delete credentials from %s: %w", store.backend, err)
	}
	return nil
}
