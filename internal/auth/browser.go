package auth

import (
	"context"
	"fmt"
	"os/exec"
)

type CommandRunner interface {
	Run(context.Context, string, ...string) error
}

type execCommandRunner struct{}

func (execCommandRunner) Run(ctx context.Context, name string, args ...string) error {
	return exec.CommandContext(ctx, name, args...).Run()
}

func NewBrowserOpener(platform string, runner CommandRunner) OpenURL {
	if runner == nil {
		runner = execCommandRunner{}
	}
	return func(ctx context.Context, loginURL string) error {
		var name string
		var args []string
		switch platform {
		case "darwin":
			name = "open"
			args = []string{loginURL}
		case "windows":
			name = "rundll32"
			args = []string{"url.dll,FileProtocolHandler", loginURL}
		case "linux":
			name = "xdg-open"
			args = []string{loginURL}
		default:
			return fmt.Errorf("unsupported browser platform %q", platform)
		}
		if err := runner.Run(ctx, name, args...); err != nil {
			return fmt.Errorf("open login page: %w", err)
		}
		return nil
	}
}
