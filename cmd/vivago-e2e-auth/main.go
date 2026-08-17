package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strings"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
	"github.com/HiDream-ai/vivago-agent-cli/internal/e2eauth"
)

const environmentVariable = "VIVAGO_E2E_TICKET"

var (
	repositoryPattern  = regexp.MustCompile(`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`)
	environmentPattern = regexp.MustCompile(`^[A-Za-z0-9_.-]+$`)
	secretPattern      = regexp.MustCompile(`^[A-Z][A-Z0-9_]+$`)
)

func main() {
	if err := run(context.Background(), os.Args[1:], os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "error: one-time E2E authentication operation failed")
		os.Exit(1)
	}
}

func run(ctx context.Context, args []string, stdout io.Writer) error {
	if len(args) == 0 {
		return fmt.Errorf("operation is required")
	}
	switch args[0] {
	case "seed":
		return runSeed(ctx, args[1:], stdout)
	case "clear":
		return runClear(ctx, args[1:], stdout)
	case "publish":
		return runPublish(ctx, args[1:], stdout)
	default:
		return fmt.Errorf("unsupported operation")
	}
}

func runClear(ctx context.Context, args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet("clear", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	profile := flags.String("profile", "dev", "credential profile")
	if flags.Parse(args) != nil || flags.NArg() != 0 || !validProfile(*profile) {
		return fmt.Errorf("invalid clear arguments")
	}
	configDirectory, err := os.UserConfigDir()
	if err != nil {
		return fmt.Errorf("resolve config directory")
	}
	backend, err := e2eauth.Clear(
		ctx,
		*profile,
		runtime.GOOS,
		configDirectory,
		auth.NewPlatformSystemKeyring(),
	)
	if err != nil {
		return err
	}
	return json.NewEncoder(stdout).Encode(map[string]any{
		"ok":      true,
		"backend": backend,
		"cleared": true,
	})
}

func runSeed(ctx context.Context, args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet("seed", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	profile := flags.String("profile", "dev", "credential profile")
	minimumValidity := flags.Duration("minimum-validity", 20*time.Minute, "minimum remaining validity")
	if flags.Parse(args) != nil || flags.NArg() != 0 || !validProfile(*profile) {
		return fmt.Errorf("invalid seed arguments")
	}
	configDirectory, err := os.UserConfigDir()
	if err != nil {
		return fmt.Errorf("resolve config directory")
	}
	backend, err := e2eauth.Seed(ctx, e2eauth.SeedOptions{
		Profile:         *profile,
		Ticket:          os.Getenv(environmentVariable),
		Platform:        runtime.GOOS,
		ConfigDirectory: configDirectory,
		SystemKeyring:   auth.NewPlatformSystemKeyring(),
		MinimumValidity: *minimumValidity,
	})
	if err != nil {
		return err
	}
	return json.NewEncoder(stdout).Encode(map[string]any{
		"ok":                       true,
		"backend":                  backend,
		"minimum_validity_seconds": int64(minimumValidity.Seconds()),
	})
}

func runPublish(ctx context.Context, args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet("publish", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	repository := flags.String("repo", "", "GitHub owner/repository")
	environment := flags.String("environment", "", "GitHub Environment name")
	secretName := flags.String("secret-name", environmentVariable, "GitHub Environment secret name")
	profile := flags.String("profile", "dev", "credential profile")
	minimumValidity := flags.Duration("minimum-validity", 45*time.Minute, "minimum remaining validity")
	if flags.Parse(args) != nil || flags.NArg() != 0 ||
		!repositoryPattern.MatchString(*repository) ||
		!environmentPattern.MatchString(*environment) ||
		!secretPattern.MatchString(*secretName) ||
		!validProfile(*profile) {
		return fmt.Errorf("invalid publish arguments")
	}
	configDirectory, err := os.UserConfigDir()
	if err != nil {
		return fmt.Errorf("resolve config directory")
	}
	ticket, backend, err := e2eauth.LoadFreshTicket(ctx, e2eauth.LoadOptions{
		Profile:         *profile,
		Platform:        runtime.GOOS,
		ConfigDirectory: configDirectory,
		SystemKeyring:   auth.NewPlatformSystemKeyring(),
		MinimumValidity: *minimumValidity,
	})
	if err != nil {
		return err
	}
	command := exec.CommandContext(
		ctx,
		"gh",
		"secret",
		"set",
		*secretName,
		"--env",
		*environment,
		"--repo",
		*repository,
	)
	command.Stdin = strings.NewReader(ticket)
	command.Stdout = io.Discard
	command.Stderr = io.Discard
	if err := command.Run(); err != nil {
		return fmt.Errorf("upload protected one-time credential")
	}
	return json.NewEncoder(stdout).Encode(map[string]any{
		"ok":                       true,
		"backend":                  backend,
		"minimum_validity_seconds": int64(minimumValidity.Seconds()),
	})
}

func validProfile(profile string) bool {
	return profile == "dev" || profile == "prod"
}
