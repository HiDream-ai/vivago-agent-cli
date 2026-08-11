package auth

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

type memoryCredentialStore struct {
	credentials Credentials
	deleted     bool
	loadErr     error
	saveErr     error
	deleteErr   error
}

func (store *memoryCredentialStore) Load(context.Context) (Credentials, error) {
	if store.loadErr != nil {
		return Credentials{}, store.loadErr
	}
	return store.credentials, nil
}

func (store *memoryCredentialStore) Save(_ context.Context, credentials Credentials) error {
	if store.saveErr != nil {
		return store.saveErr
	}
	store.credentials = credentials
	return nil
}

func (store *memoryCredentialStore) Delete(context.Context) error {
	if store.deleteErr != nil {
		return store.deleteErr
	}
	store.deleted = true
	store.credentials = Credentials{}
	return nil
}

func (store *memoryCredentialStore) Backend() string {
	return "memory"
}

type queuedTokenRefresher struct {
	results []string
	errors  []error
	calls   int
}

func (refresher *queuedTokenRefresher) Refresh(context.Context, string) (string, error) {
	index := refresher.calls
	refresher.calls++
	return refresher.results[index], refresher.errors[index]
}

func TestStoredAuthProviderRetriesTransientRefreshOnceAndPersistsTicket(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       unsignedTestJWT(now.Add(-time.Minute)),
		RefreshToken: "test-refresh-token",
	}}
	newTicket := unsignedTestJWT(now.Add(time.Hour))
	refresher := &queuedTokenRefresher{
		results: []string{"", newTicket},
		errors: []error{
			&RefreshError{Kind: RefreshFailureTransient},
			nil,
		},
	}
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{
		Now:        func() time.Time { return now },
		RetryDelay: 0,
	})

	ticket, err := provider.AccessToken(context.Background())
	if err != nil {
		t.Fatalf("access token: %v", err)
	}
	if ticket != newTicket {
		t.Fatalf("ticket = %q", ticket)
	}
	if refresher.calls != 2 {
		t.Fatalf("refresh calls = %d, want 2", refresher.calls)
	}
	if store.credentials.Ticket != newTicket || store.credentials.RefreshToken != "test-refresh-token" {
		t.Fatalf("stored credentials = %#v", store.credentials)
	}
	if store.deleted {
		t.Fatal("credentials were deleted after successful refresh")
	}
}

func TestStoredAuthProviderHoldsProcessLockDuringRefresh(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       unsignedTestJWT(now.Add(-time.Minute)),
		RefreshToken: "test-refresh-token",
	}}
	processLock := &recordingProcessLock{}
	newTicket := unsignedTestJWT(now.Add(time.Hour))
	refresher := tokenRefresherFunc(func(context.Context, string) (string, error) {
		if !processLock.held {
			t.Fatal("token refreshed without process lock")
		}
		return newTicket, nil
	})
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{
		Now:  func() time.Time { return now },
		Lock: processLock,
	})

	ticket, err := provider.AccessToken(context.Background())
	if err != nil {
		t.Fatalf("access token: %v", err)
	}
	if ticket != newTicket || processLock.calls != 1 || processLock.held {
		t.Fatalf("ticket = %q, lock calls = %d, held = %v", ticket, processLock.calls, processLock.held)
	}
}

func TestStoredAuthProviderManualRefreshForcesValidTicketInsideProcessLock(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	oldTicket := unsignedTestJWT(now.Add(time.Hour))
	newTicket := unsignedTestJWT(now.Add(2 * time.Hour))
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       oldTicket,
		RefreshToken: "test-refresh-token",
	}}
	processLock := &recordingProcessLock{}
	refresher := tokenRefresherFunc(func(_ context.Context, refreshToken string) (string, error) {
		if !processLock.held {
			t.Fatal("manual refresh ran without the process lock")
		}
		if refreshToken != "test-refresh-token" {
			t.Fatalf("refresh token = %q", refreshToken)
		}
		return newTicket, nil
	})
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{
		Now:  func() time.Time { return now },
		Lock: processLock,
	})

	if err := provider.Refresh(context.Background()); err != nil {
		t.Fatalf("manual refresh: %v", err)
	}
	if processLock.calls != 1 || processLock.held {
		t.Fatalf("lock calls = %d, held = %v", processLock.calls, processLock.held)
	}
	if store.credentials.Ticket != newTicket {
		t.Fatalf("stored ticket was not replaced")
	}
}

func TestStoredAuthProviderManualRefreshRequiresExistingCredentials(t *testing.T) {
	store := &memoryCredentialStore{loadErr: ErrCredentialsNotFound}
	refresher := &queuedTokenRefresher{}
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{})

	err := provider.Refresh(context.Background())
	if !errors.Is(err, ErrLoginRequired) {
		t.Fatalf("error = %v, want login required", err)
	}
	if refresher.calls != 0 {
		t.Fatalf("refresh calls = %d, want 0", refresher.calls)
	}
}

func TestStoredAuthProviderManualRefreshClearsRejectedCredentials(t *testing.T) {
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       "old-ticket",
		RefreshToken: "test-refresh-token",
	}}
	refresher := &queuedTokenRefresher{
		results: []string{""},
		errors:  []error{&RefreshError{Kind: RefreshFailureInvalid}},
	}
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{})

	err := provider.Refresh(context.Background())
	if !errors.Is(err, ErrLoginRequired) {
		t.Fatalf("error = %v, want login required", err)
	}
	if !store.deleted {
		t.Fatal("rejected credentials were not deleted")
	}
}

func TestStoredAuthProviderManualRefreshRetriesTransientFailureOnce(t *testing.T) {
	store := &memoryCredentialStore{credentials: Credentials{
		Ticket:       "old-ticket",
		RefreshToken: "test-refresh-token",
	}}
	refresher := &queuedTokenRefresher{
		results: []string{"", "new-ticket"},
		errors: []error{
			&RefreshError{Kind: RefreshFailureTransient},
			nil,
		},
	}
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{RetryDelay: 0})

	if err := provider.Refresh(context.Background()); err != nil {
		t.Fatalf("manual refresh: %v", err)
	}
	if refresher.calls != 2 || store.credentials.Ticket != "new-ticket" {
		t.Fatalf("refresh calls = %d, credentials = %#v", refresher.calls, store.credentials)
	}
}

func TestStoredAuthProviderManualRefreshReportsSaveFailureWithoutReturningTicket(t *testing.T) {
	store := &memoryCredentialStore{
		credentials: Credentials{Ticket: "old-ticket", RefreshToken: "test-refresh-token"},
		saveErr:     errors.New("test save failure"),
	}
	refresher := &queuedTokenRefresher{
		results: []string{"secret-new-ticket"},
		errors:  []error{nil},
	}
	provider := NewStoredAuthProvider(store, refresher, ProviderOptions{})

	err := provider.Refresh(context.Background())
	if err == nil || !strings.Contains(err.Error(), "save refreshed authentication") {
		t.Fatalf("error = %v", err)
	}
	if strings.Contains(err.Error(), "secret-new-ticket") {
		t.Fatalf("error exposes refreshed ticket: %v", err)
	}
}

type tokenRefresherFunc func(context.Context, string) (string, error)

func (function tokenRefresherFunc) Refresh(ctx context.Context, token string) (string, error) {
	return function(ctx, token)
}
