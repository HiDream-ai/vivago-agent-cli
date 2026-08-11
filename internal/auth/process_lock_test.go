package auth

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestFileProcessLockSerializesIndependentInstances(t *testing.T) {
	lockPath := filepath.Join(t.TempDir(), "vivago-agent", "auth-dev.lock")
	first := NewFileProcessLock(lockPath)
	second := NewFileProcessLock(lockPath)
	firstEntered := make(chan struct{})
	releaseFirst := make(chan struct{})
	firstDone := make(chan error, 1)
	go func() {
		firstDone <- first.WithLock(context.Background(), func() error {
			close(firstEntered)
			<-releaseFirst
			return nil
		})
	}()
	<-firstEntered

	secondContext, cancel := context.WithTimeout(context.Background(), 40*time.Millisecond)
	defer cancel()
	secondEntered := false
	err := second.WithLock(secondContext, func() error {
		secondEntered = true
		return nil
	})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("second lock error = %v, want deadline exceeded", err)
	}
	if secondEntered {
		t.Fatal("second critical section entered while first lock was held")
	}

	close(releaseFirst)
	if err := <-firstDone; err != nil {
		t.Fatalf("first lock: %v", err)
	}
	if err := second.WithLock(context.Background(), func() error {
		secondEntered = true
		return nil
	}); err != nil {
		t.Fatalf("second lock after release: %v", err)
	}
	if !secondEntered {
		t.Fatal("second critical section did not enter after release")
	}

	directoryInfo, err := os.Stat(filepath.Dir(lockPath))
	if err != nil {
		t.Fatalf("stat lock directory: %v", err)
	}
	if directoryInfo.Mode().Perm() != 0o700 {
		t.Fatalf("lock directory permissions = %04o", directoryInfo.Mode().Perm())
	}
	fileInfo, err := os.Stat(lockPath)
	if err != nil {
		t.Fatalf("stat lock file: %v", err)
	}
	if fileInfo.Mode().Perm() != 0o600 {
		t.Fatalf("lock file permissions = %04o", fileInfo.Mode().Perm())
	}
}

func TestFileProcessLockDoesNotRequirePOSIXModesOnWindows(t *testing.T) {
	directory := filepath.Join(t.TempDir(), "vivago-agent")
	if err := os.Mkdir(directory, 0o755); err != nil {
		t.Fatalf("create lock directory: %v", err)
	}
	lockPath := filepath.Join(directory, "auth-dev.lock")
	if err := os.WriteFile(lockPath, nil, 0o644); err != nil {
		t.Fatalf("create lock file: %v", err)
	}
	lock := newFileProcessLock(lockPath, "windows")
	entered := false
	if err := lock.WithLock(context.Background(), func() error {
		entered = true
		return nil
	}); err != nil {
		t.Fatalf("windows lock rejected non-POSIX modes: %v", err)
	}
	if !entered {
		t.Fatal("windows lock did not enter critical section")
	}
}
