//go:build !prod

package main

import (
	"bytes"
	"context"
	"io"
	"testing"

	"github.com/HiDream-ai/vivago-agent-cli/internal/cli"
)

func TestDevelopmentAuthRefreshInitializesAuthenticationRuntime(t *testing.T) {
	var stdout bytes.Buffer
	factoryCalls := 0

	exitCode := runWithAuthFactory(
		context.Background(),
		[]string{"--json", "auth", "refresh"},
		&stdout,
		&bytes.Buffer{},
		func(context.Context, io.Writer) (cli.AuthRuntime, error) {
			factoryCalls++
			return &mainTestAuthRuntime{}, nil
		},
	)

	if exitCode != 0 || factoryCalls != 1 {
		t.Fatalf("exit = %d, factory calls = %d, stdout = %s", exitCode, factoryCalls, stdout.String())
	}
}
