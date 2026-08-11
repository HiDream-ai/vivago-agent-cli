package auth

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/gofrs/flock"
)

const processLockRetryDelay = 10 * time.Millisecond

type ProcessLock interface {
	WithLock(context.Context, func() error) error
}

type noopProcessLock struct{}

func (noopProcessLock) WithLock(_ context.Context, operation func() error) error {
	return operation()
}

type FileProcessLock struct {
	path     string
	platform string
}

func NewFileProcessLock(path string) *FileProcessLock {
	return newFileProcessLock(path, runtime.GOOS)
}

func newFileProcessLock(path, platform string) *FileProcessLock {
	return &FileProcessLock{path: path, platform: platform}
}

func (lock *FileProcessLock) WithLock(ctx context.Context, operation func() error) (resultErr error) {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := prepareProcessLock(lock.path, lock.platform); err != nil {
		return err
	}

	fileLock := flock.New(lock.path, flock.SetPermissions(0o600))
	locked, err := fileLock.TryLockContext(ctx, processLockRetryDelay)
	if err != nil {
		return fmt.Errorf("acquire authentication lock: %w", err)
	}
	if !locked {
		return fmt.Errorf("acquire authentication lock")
	}
	defer func() {
		if err := fileLock.Unlock(); err != nil && resultErr == nil {
			resultErr = fmt.Errorf("release authentication lock: %w", err)
		}
	}()
	if lock.platform != "windows" {
		if err := os.Chmod(lock.path, 0o600); err != nil {
			return fmt.Errorf("set authentication lock permissions: %w", err)
		}
	}
	return operation()
}

func prepareProcessLock(path, platform string) error {
	directory := filepath.Dir(path)
	directoryInfo, err := os.Lstat(directory)
	if errors.Is(err, os.ErrNotExist) {
		if err := os.MkdirAll(directory, 0o700); err != nil {
			return fmt.Errorf("create authentication lock directory: %w", err)
		}
		directoryInfo, err = os.Lstat(directory)
	}
	if err != nil {
		return fmt.Errorf("inspect authentication lock directory: %w", err)
	}
	if directoryInfo.Mode()&os.ModeSymlink != 0 || !directoryInfo.IsDir() {
		return fmt.Errorf("authentication lock directory must be a real directory")
	}
	if platform != "windows" {
		if err := os.Chmod(directory, 0o700); err != nil {
			return fmt.Errorf("set authentication lock directory permissions: %w", err)
		}
	}

	fileInfo, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect authentication lock file: %w", err)
	}
	if fileInfo.Mode()&os.ModeSymlink != 0 || !fileInfo.Mode().IsRegular() {
		return fmt.Errorf("authentication lock file must be a regular file")
	}
	if platform != "windows" && fileInfo.Mode().Perm() != 0o600 {
		return fmt.Errorf("authentication lock file permissions must be 0600")
	}
	return nil
}
