package auth

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestServiceStatusReportsBackendAndLoginStateWithoutCredentials(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       unsignedTestJWT(now.Add(time.Hour)),
		RefreshToken: "test-refresh-token",
	}}
	service := NewService(store, func() time.Time { return now })

	status, err := service.Status(context.Background())
	if err != nil {
		t.Fatalf("status: %v", err)
	}
	if !status.LoggedIn || status.Backend != "memory" || status.NeedsRefresh {
		t.Fatalf("status = %#v", status)
	}
}

func TestServiceStatusTreatsMissingCredentialsAsLoggedOut(t *testing.T) {
	store := &missingCredentialStore{}
	service := NewService(store, nil)

	status, err := service.Status(context.Background())
	if err != nil {
		t.Fatalf("status: %v", err)
	}
	if status.LoggedIn || status.Backend != "missing" {
		t.Fatalf("status = %#v", status)
	}
}

func TestServiceLogoutDeletesOnlyLocalCredentials(t *testing.T) {
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       "test-ticket",
		RefreshToken: "test-refresh-token",
	}}
	service := NewService(store, nil)

	if err := service.Logout(context.Background()); err != nil {
		t.Fatalf("logout: %v", err)
	}
	if !store.deleted {
		t.Fatal("credentials were not deleted")
	}
}

type missingCredentialStore struct{}

func (*missingCredentialStore) Load(context.Context) (Credentials, error) {
	return Credentials{}, ErrCredentialsNotFound
}

func (*missingCredentialStore) Save(context.Context, Credentials) error {
	return errors.New("unexpected save")
}

func (*missingCredentialStore) Delete(context.Context) error {
	return nil
}

func (*missingCredentialStore) Backend() string {
	return "missing"
}
