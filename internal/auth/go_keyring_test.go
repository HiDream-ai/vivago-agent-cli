package auth

import (
	"context"
	"errors"
	"testing"

	keyring "github.com/zalando/go-keyring"
)

func TestGoKeyringAdapterMapsNotFoundAndHonorsContext(t *testing.T) {
	raw := &fakeGoKeyring{getError: keyring.ErrNotFound}
	adapter := newGoKeyringAdapter(raw)

	_, err := adapter.Get(context.Background(), "test-service", "test-account")
	if !errors.Is(err, ErrSystemKeyringItemNotFound) {
		t.Fatalf("get error = %v, want ErrSystemKeyringItemNotFound", err)
	}

	cancelled, cancel := context.WithCancel(context.Background())
	cancel()
	raw.getCalls = 0
	_, err = adapter.Get(cancelled, "test-service", "test-account")
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("cancelled get error = %v", err)
	}
	if raw.getCalls != 0 {
		t.Fatalf("cancelled get called backend %d times", raw.getCalls)
	}
}

func TestProbeSystemKeyringDistinguishesMissingItemFromUnavailableBackend(t *testing.T) {
	profile := CredentialProfile{Service: "test-service", Account: "test-account"}

	missing := newGoKeyringAdapter(&fakeGoKeyring{getError: keyring.ErrNotFound})
	if err := ProbeSystemKeyring(context.Background(), missing, profile); err != nil {
		t.Fatalf("missing item should prove backend availability: %v", err)
	}

	unavailable := newGoKeyringAdapter(&fakeGoKeyring{getError: errors.New("dbus unavailable")})
	if err := ProbeSystemKeyring(context.Background(), unavailable, profile); err == nil {
		t.Fatal("unavailable backend passed probe")
	}
}

type fakeGoKeyring struct {
	getValue string
	getError error
	getCalls int
}

func (backend *fakeGoKeyring) Get(string, string) (string, error) {
	backend.getCalls++
	return backend.getValue, backend.getError
}

func (*fakeGoKeyring) Set(string, string, string) error {
	return nil
}

func (*fakeGoKeyring) Delete(string, string) error {
	return nil
}
