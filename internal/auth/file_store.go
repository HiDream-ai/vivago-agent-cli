package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type FileCredentialStore struct {
	path string
}

func NewFileCredentialStore(path string) *FileCredentialStore {
	return &FileCredentialStore{path: path}
}

func (store *FileCredentialStore) Backend() string {
	return "file"
}

func (store *FileCredentialStore) Save(ctx context.Context, credentials Credentials) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if strings.TrimSpace(credentials.Ticket) == "" || strings.TrimSpace(credentials.RefreshToken) == "" {
		return fmt.Errorf("ticket and refresh token are required")
	}
	directory := filepath.Dir(store.path)
	if err := ensurePrivateDirectory(directory); err != nil {
		return err
	}
	if err := validateCredentialTarget(store.path, true); err != nil {
		return err
	}
	payload, err := json.Marshal(credentials)
	if err != nil {
		return fmt.Errorf("encode credentials: %w", err)
	}

	temporary, err := os.CreateTemp(directory, ".credentials-*")
	if err != nil {
		return fmt.Errorf("create temporary credential file: %w", err)
	}
	temporaryPath := temporary.Name()
	removeTemporary := true
	defer func() {
		if removeTemporary {
			_ = os.Remove(temporaryPath)
		}
	}()
	if err := temporary.Chmod(0o600); err != nil {
		_ = temporary.Close()
		return fmt.Errorf("set temporary credential permissions: %w", err)
	}
	if _, err := temporary.Write(payload); err != nil {
		_ = temporary.Close()
		return fmt.Errorf("write temporary credentials: %w", err)
	}
	if err := temporary.Sync(); err != nil {
		_ = temporary.Close()
		return fmt.Errorf("sync temporary credentials: %w", err)
	}
	if err := temporary.Close(); err != nil {
		return fmt.Errorf("close temporary credentials: %w", err)
	}
	if err := os.Rename(temporaryPath, store.path); err != nil {
		return fmt.Errorf("replace credential file: %w", err)
	}
	removeTemporary = false
	return nil
}

func (store *FileCredentialStore) Load(ctx context.Context) (Credentials, error) {
	if err := ctx.Err(); err != nil {
		return Credentials{}, err
	}
	if err := validateCredentialTarget(store.path, false); err != nil {
		return Credentials{}, err
	}
	payload, err := os.ReadFile(store.path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return Credentials{}, ErrCredentialsNotFound
		}
		return Credentials{}, fmt.Errorf("read credentials: %w", err)
	}
	var credentials Credentials
	if err := json.Unmarshal(payload, &credentials); err != nil {
		return Credentials{}, fmt.Errorf("decode credentials: %w", err)
	}
	if credentials.Ticket == "" || credentials.RefreshToken == "" {
		return Credentials{}, fmt.Errorf("credential file is incomplete")
	}
	return credentials, nil
}

func (store *FileCredentialStore) Delete(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := validateCredentialTarget(store.path, true); err != nil {
		return err
	}
	if err := os.Remove(store.path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("delete credentials: %w", err)
	}
	return nil
}

func ensurePrivateDirectory(path string) error {
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		if err := os.MkdirAll(path, 0o700); err != nil {
			return fmt.Errorf("create credential directory: %w", err)
		}
		info, err = os.Lstat(path)
	}
	if err != nil {
		return fmt.Errorf("inspect credential directory: %w", err)
	}
	if info.Mode()&os.ModeSymlink != 0 || !info.IsDir() {
		return fmt.Errorf("credential directory must be a real directory")
	}
	if err := os.Chmod(path, 0o700); err != nil {
		return fmt.Errorf("set credential directory permissions: %w", err)
	}
	return nil
}

func validateCredentialTarget(path string, allowMissing bool) error {
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) && allowMissing {
		return nil
	}
	if errors.Is(err, os.ErrNotExist) {
		return ErrCredentialsNotFound
	}
	if err != nil {
		return fmt.Errorf("inspect credential file: %w", err)
	}
	if info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() {
		return fmt.Errorf("credential file must be a regular file")
	}
	if info.Mode().Perm() != 0o600 {
		return fmt.Errorf("credential file permissions must be 0600")
	}
	return nil
}
