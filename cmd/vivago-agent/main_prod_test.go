//go:build prod

package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"strings"
	"testing"

	"github.com/HiDream-ai/vivago-agent-cli/internal/cli"
)

func TestProductionAuthRefreshDoesNotInitializeRuntime(t *testing.T) {
	for _, args := range [][]string{
		{"--json", "auth", "refresh"},
		{"--json", "auth", "refresh", "--unexpected"},
	} {
		var stdout bytes.Buffer
		factoryCalls := 0
		exitCode := runWithRuntimeFactory(
			context.Background(),
			args,
			&stdout,
			&bytes.Buffer{},
			func(context.Context, io.Writer) (cli.Runtime, error) {
				factoryCalls++
				return cli.Runtime{}, errors.New("production refresh must not initialize credentials")
			},
		)

		if exitCode != 2 || factoryCalls != 0 {
			t.Fatalf("args = %v, exit = %d, factory calls = %d, stdout = %s", args, exitCode, factoryCalls, stdout.String())
		}
		if !strings.Contains(stdout.String(), `"code":"COMMAND_UNAVAILABLE"`) {
			t.Fatalf("args = %v, stdout = %s", args, stdout.String())
		}
	}
}
