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
	values map[string]string
}

func (keyring *memoryKeyring) Get(_ context.Context, service, account string) (string, error) {
	value := keyring.values[service+"/"+account]
	if value == "" {
		return "", auth.ErrSystemKeyringItemNotFound
	}
	return value, nil
}

func (keyring *memoryKeyring) Set(_ context.Context, service, account, value string) error {
	if keyring.values == nil {
		keyring.values = make(map[string]string)
	}
	keyring.values[service+"/"+account] = value
	return nil
}

func (keyring *memoryKeyring) Delete(_ context.Context, service, account string) error {
	delete(keyring.values, service+"/"+account)
	return nil
}

func (keyring *memoryKeyring) value(service, account string) string {
	return keyring.values[service+"/"+account]
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
		Profile:         "dev",
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
	stored := keyring.value("ai.hidream.vivago-agent.dev", "overseas-dev")
	if !strings.Contains(stored, ticket) {
		t.Fatal("system credential does not contain the supplied ticket")
	}
	if !strings.Contains(stored, DisabledRefreshToken) {
		t.Fatal("system credential does not contain the disabled refresh sentinel")
	}
}

func TestSeedRejectsExpiringTicketWithoutExposingIt(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	ticket := testTicket(now.Add(5 * time.Minute))

	_, err := Seed(context.Background(), SeedOptions{
		Profile:         "dev",
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
		Profile:         "dev",
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
		Profile:         "dev",
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

	backend, err := Clear(context.Background(), "dev", "darwin", configDirectory, keyring)
	if err != nil {
		t.Fatalf("Clear: %v", err)
	}
	if backend != "keychain" || keyring.value("ai.hidream.vivago-agent.dev", "overseas-dev") != "" {
		t.Fatalf("credential was not cleared: backend=%q", backend)
	}
}

func TestProfilesUseIndependentCredentialNamespaces(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	devTicket := testTicket(now.Add(time.Hour))
	prodTicket := testTicket(now.Add(2 * time.Hour))
	keyring := &memoryKeyring{}
	configDirectory := t.TempDir()

	for profile, ticket := range map[string]string{
		"dev":  devTicket,
		"prod": prodTicket,
	} {
		if _, err := Seed(context.Background(), SeedOptions{
			Profile:         profile,
			Ticket:          ticket,
			Platform:        "darwin",
			ConfigDirectory: configDirectory,
			SystemKeyring:   keyring,
			Now:             now,
			MinimumValidity: 20 * time.Minute,
		}); err != nil {
			t.Fatalf("Seed(%s): %v", profile, err)
		}
	}

	for profile, want := range map[string]string{
		"dev":  devTicket,
		"prod": prodTicket,
	} {
		got, backend, err := LoadFreshTicket(context.Background(), LoadOptions{
			Profile:         profile,
			Platform:        "darwin",
			ConfigDirectory: configDirectory,
			SystemKeyring:   keyring,
			Now:             now,
			MinimumValidity: 20 * time.Minute,
		})
		if err != nil {
			t.Fatalf("LoadFreshTicket(%s): %v", profile, err)
		}
		if got != want || backend != "keychain" {
			t.Fatalf("LoadFreshTicket(%s) = redacted-match:%t, %q", profile, got == want, backend)
		}
	}

	if _, err := Clear(context.Background(), "prod", "darwin", configDirectory, keyring); err != nil {
		t.Fatalf("Clear(prod): %v", err)
	}
	if keyring.value("ai.hidream.vivago-agent", "overseas-prod") != "" {
		t.Fatal("production credential was not cleared")
	}
	if keyring.value("ai.hidream.vivago-agent.dev", "overseas-dev") == "" {
		t.Fatal("clearing production credential deleted development credential")
	}
}

func TestSeedRejectsUnsupportedProfileWithoutExposingTicket(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	ticket := testTicket(now.Add(time.Hour))

	_, err := Seed(context.Background(), SeedOptions{
		Profile:         "staging",
		Ticket:          ticket,
		Platform:        "darwin",
		ConfigDirectory: t.TempDir(),
		SystemKeyring:   &memoryKeyring{},
		Now:             now,
		MinimumValidity: 20 * time.Minute,
	})
	if err == nil {
		t.Fatal("unsupported profile was accepted")
	}
	if strings.Contains(err.Error(), ticket) {
		t.Fatal("error exposes the supplied ticket")
	}
}
