package e2eauth

import (
	"context"
	"encoding/base64"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
)

type memoryKeyring struct {
	value string
}

func (keyring *memoryKeyring) Get(context.Context, string, string) (string, error) {
	if keyring.value == "" {
		return "", auth.ErrSystemKeyringItemNotFound
	}
	return keyring.value, nil
}

func (keyring *memoryKeyring) Set(_ context.Context, _, _, value string) error {
	keyring.value = value
	return nil
}

func (keyring *memoryKeyring) Delete(context.Context, string, string) error {
	keyring.value = ""
	return nil
}

func testTicket(expiry time.Time) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"none"}`))
	payload := base64.RawURLEncoding.EncodeToString(
		[]byte(fmt.Sprintf(`{"exp":%d}`, expiry.Unix())),
	)
	return header + "." + payload + ".signature"
}

func TestSeedStoresOnlyFreshTicketWithDisabledRefreshSentinel(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	ticket := testTicket(now.Add(time.Hour))
	keyring := &memoryKeyring{}

	backend, err := Seed(context.Background(), SeedOptions{
		Ticket:          ticket,
		Platform:        "darwin",
		ConfigDirectory: t.TempDir(),
		SystemKeyring:   keyring,
		Now:             now,
		MinimumValidity: 20 * time.Minute,
	})
	if err != nil {
		t.Fatalf("Seed: %v", err)
	}
	if backend != "keychain" {
		t.Fatalf("backend = %q", backend)
	}
	if !strings.Contains(keyring.value, ticket) {
		t.Fatal("system credential does not contain the supplied ticket")
	}
	if !strings.Contains(keyring.value, DisabledRefreshToken) {
		t.Fatal("system credential does not contain the disabled refresh sentinel")
	}
}

func TestSeedRejectsExpiringTicketWithoutExposingIt(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	ticket := testTicket(now.Add(5 * time.Minute))

	_, err := Seed(context.Background(), SeedOptions{
		Ticket:          ticket,
		Platform:        "darwin",
		ConfigDirectory: t.TempDir(),
		SystemKeyring:   &memoryKeyring{},
		Now:             now,
		MinimumValidity: 20 * time.Minute,
	})
	if err == nil {
		t.Fatal("expiring ticket was accepted")
	}
	if strings.Contains(err.Error(), ticket) {
		t.Fatal("error exposes the supplied ticket")
	}
}

func TestSeedRejectsMissingTicket(t *testing.T) {
	_, err := Seed(context.Background(), SeedOptions{
		Platform:        "linux",
		ConfigDirectory: t.TempDir(),
		Now:             time.Now(),
		MinimumValidity: time.Minute,
	})
	if err == nil {
		t.Fatal("missing ticket was accepted")
	}
}

func TestClearDeletesSeededCredential(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	keyring := &memoryKeyring{}
	configDirectory := t.TempDir()
	_, err := Seed(context.Background(), SeedOptions{
		Ticket:          testTicket(now.Add(time.Hour)),
		Platform:        "darwin",
		ConfigDirectory: configDirectory,
		SystemKeyring:   keyring,
		Now:             now,
		MinimumValidity: 20 * time.Minute,
	})
	if err != nil {
		t.Fatalf("Seed: %v", err)
	}

	backend, err := Clear(context.Background(), "darwin", configDirectory, keyring)
	if err != nil {
		t.Fatalf("Clear: %v", err)
	}
	if backend != "keychain" || keyring.value != "" {
		t.Fatalf("credential was not cleared: backend=%q value=%q", backend, keyring.value)
	}
}
