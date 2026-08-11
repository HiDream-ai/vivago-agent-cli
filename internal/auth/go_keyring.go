package auth

import (
	"context"
	"errors"
	"fmt"

	keyring "github.com/zalando/go-keyring"
)

type rawGoKeyring interface {
	Get(string, string) (string, error)
	Set(string, string, string) error
	Delete(string, string) error
}

type packageGoKeyring struct{}

func (packageGoKeyring) Get(service, account string) (string, error) {
	return keyring.Get(service, account)
}

func (packageGoKeyring) Set(service, account, secret string) error {
	return keyring.Set(service, account, secret)
}

func (packageGoKeyring) Delete(service, account string) error {
	return keyring.Delete(service, account)
}

type goKeyringAdapter struct {
	backend rawGoKeyring
}

func NewPlatformSystemKeyring() SystemKeyring {
	return newGoKeyringAdapter(packageGoKeyring{})
}

func newGoKeyringAdapter(backend rawGoKeyring) SystemKeyring {
	return &goKeyringAdapter{backend: backend}
}

func (adapter *goKeyringAdapter) Get(ctx context.Context, service, account string) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	secret, err := adapter.backend.Get(service, account)
	if errors.Is(err, keyring.ErrNotFound) {
		return "", ErrSystemKeyringItemNotFound
	}
	if err != nil {
		return "", fmt.Errorf("read system credential: %w", err)
	}
	return secret, nil
}

func (adapter *goKeyringAdapter) Set(ctx context.Context, service, account, secret string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := adapter.backend.Set(service, account, secret); err != nil {
		return fmt.Errorf("write system credential: %w", err)
	}
	return nil
}

func (adapter *goKeyringAdapter) Delete(ctx context.Context, service, account string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := adapter.backend.Delete(service, account); err != nil {
		if errors.Is(err, keyring.ErrNotFound) {
			return ErrSystemKeyringItemNotFound
		}
		return fmt.Errorf("delete system credential: %w", err)
	}
	return nil
}

func ProbeSystemKeyring(ctx context.Context, systemKeyring SystemKeyring, profile CredentialProfile) error {
	_, err := systemKeyring.Get(ctx, profile.Service, profile.Account)
	if errors.Is(err, ErrSystemKeyringItemNotFound) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("probe system credential store: %w", err)
	}
	return nil
}
