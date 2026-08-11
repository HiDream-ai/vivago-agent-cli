//go:build !windows

package auth

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestFileCredentialStoreSavesAndLoadsWithPrivatePermissions(t *testing.T) {
	credentialDir := filepath.Join(t.TempDir(), "vivago-agent")
	credentialPath := filepath.Join(credentialDir, "credentials-dev.json")
	store := NewFileCredentialStore(credentialPath)
	want := Credentials{
		Ticket:       "test-ticket",
		RefreshToken: "test-refresh-token",
	}

	if err := store.Save(context.Background(), want); err != nil {
		t.Fatalf("save credentials: %v", err)
	}
	directoryInfo, err := os.Lstat(credentialDir)
	if err != nil {
		t.Fatalf("stat credential directory: %v", err)
	}
	if directoryInfo.Mode().Perm() != 0o700 {
		t.Fatalf("directory permissions = %04o, want 0700", directoryInfo.Mode().Perm())
	}
	fileInfo, err := os.Lstat(credentialPath)
	if err != nil {
		t.Fatalf("stat credential file: %v", err)
	}
	if fileInfo.Mode().Perm() != 0o600 {
		t.Fatalf("file permissions = %04o, want 0600", fileInfo.Mode().Perm())
	}

	got, err := store.Load(context.Background())
	if err != nil {
		t.Fatalf("load credentials: %v", err)
	}
	if got != want {
		t.Fatalf("credentials = %#v, want %#v", got, want)
	}
}

func TestFileCredentialStoreRejectsSymlinkTarget(t *testing.T) {
	directory := t.TempDir()
	realPath := filepath.Join(directory, "real-credentials.json")
	linkPath := filepath.Join(directory, "credentials.json")
	if err := os.WriteFile(realPath, []byte(`{"ticket":"original","refresh_token":"original"}`), 0o600); err != nil {
		t.Fatalf("write target: %v", err)
	}
	if err := os.Symlink(realPath, linkPath); err != nil {
		t.Fatalf("create symlink: %v", err)
	}
	store := NewFileCredentialStore(linkPath)

	if _, err := store.Load(context.Background()); err == nil {
		t.Fatal("load through symlink succeeded")
	}
	if err := store.Save(context.Background(), Credentials{
		Ticket:       "replacement",
		RefreshToken: "replacement",
	}); err == nil {
		t.Fatal("save through symlink succeeded")
	}
	payload, err := os.ReadFile(realPath)
	if err != nil {
		t.Fatalf("read target: %v", err)
	}
	if string(payload) != `{"ticket":"original","refresh_token":"original"}` {
		t.Fatalf("symlink target was modified: %s", payload)
	}
}
