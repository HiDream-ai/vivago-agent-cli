package main

import (
	"context"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
	"github.com/HiDream-ai/vivago-agent-cli/internal/cli"
	"github.com/HiDream-ai/vivago-agent-cli/internal/client"
	"github.com/HiDream-ai/vivago-agent-cli/internal/config"
	"github.com/HiDream-ai/vivago-agent-cli/internal/upload"
)

var (
	version = "dev"
	gitSHA  = "unknown"
	channel = "dev"
)

func run(args []string, stdout, stderr io.Writer) int {
	return runWithRuntimeFactory(context.Background(), args, stdout, stderr, newRuntime)
}

type authRuntimeFactory func(context.Context, io.Writer) (cli.AuthRuntime, error)
type runtimeFactory func(context.Context, io.Writer) (cli.Runtime, error)

func runWithAuthFactory(
	ctx context.Context,
	args []string,
	stdout, stderr io.Writer,
	factory authRuntimeFactory,
) int {
	return runWithRuntimeFactory(
		ctx,
		args,
		stdout,
		stderr,
		func(ctx context.Context, stderr io.Writer) (cli.Runtime, error) {
			authRuntime, err := factory(ctx, stderr)
			return cli.Runtime{Auth: authRuntime}, err
		},
	)
}

func runWithRuntimeFactory(
	ctx context.Context,
	args []string,
	stdout, stderr io.Writer,
	factory runtimeFactory,
) int {
	applicationProfile := config.Current()
	commandRuntime := cli.Runtime{
		Profile:    applicationProfile.Name,
		WebBaseURL: applicationProfile.WebBaseURL,
	}
	if requiresRuntime(args) {
		resolvedRuntime, err := factory(ctx, stderr)
		if err != nil {
			_, _ = fmt.Fprintf(
				stderr,
				"VivagoAgent runtime is unavailable on %s; verify operating-system dependencies.\n",
				runtime.GOOS,
			)
		} else {
			commandRuntime = resolvedRuntime
		}
	}
	return cli.RunContext(
		ctx,
		args,
		stdout,
		stderr,
		cli.BuildInfo{Version: version},
		commandRuntime,
	)
}

func requiresRuntime(args []string) bool {
	if len(args) < 2 {
		return false
	}
	if args[0] == "--jsonl" {
		return args[1] == "ask" || args[1] == "resume"
	}
	if len(args) >= 3 && args[0] == "--json" && args[1] == "project" && args[2] == "link" {
		return false
	}
	return args[0] == "--json" &&
		(args[1] == "auth" || args[1] == "project" || args[1] == "doctor" ||
			args[1] == "cancel" || args[1] == "history")
}

func newAuthRuntime(ctx context.Context, stderr io.Writer) (cli.AuthRuntime, error) {
	commandRuntime, err := newRuntime(ctx, stderr)
	return commandRuntime.Auth, err
}

func newRuntime(ctx context.Context, stderr io.Writer) (cli.Runtime, error) {
	applicationProfile := config.Current()
	configDirectory, err := os.UserConfigDir()
	if err != nil {
		return cli.Runtime{}, fmt.Errorf("resolve user config directory: %w", err)
	}
	credentialProfile, err := auth.ResolveCredentialProfile(applicationProfile.Name, configDirectory)
	if err != nil {
		return cli.Runtime{}, err
	}
	doctor := &doctorRuntime{
		version:           version,
		gitSHA:            gitSHA,
		channel:           channel,
		profile:           applicationProfile.Name,
		platform:          runtime.GOOS,
		architecture:      runtime.GOARCH,
		credentialBackend: credentialBackendForPlatform(runtime.GOOS),
	}
	systemKeyring := auth.NewPlatformSystemKeyring()
	probeError := auth.ProbeSystemKeyring(ctx, systemKeyring, credentialProfile)
	store, err := auth.SelectCredentialStore(
		runtime.GOOS,
		credentialProfile,
		systemKeyring,
		probeError,
	)
	if err != nil {
		return cli.Runtime{Doctor: doctor}, nil
	}
	processLock := auth.NewFileProcessLock(credentialProfile.LockPath)
	httpClient := newHTTPClient()
	host := normalizedHost(os.Getenv("VIVAGO_AGENT_HOST"))
	userAgent := fmt.Sprintf(
		"vivago-agent-cli/%s (%s; %s; %s)",
		version,
		runtime.GOOS,
		runtime.GOARCH,
		host,
	)
	tokenProvider := auth.NewStoredAuthProvider(
		store,
		auth.NewHTTPTokenRefresher(applicationProfile.APIBaseURL, httpClient, userAgent),
		auth.ProviderOptions{RetryDelay: 250 * time.Millisecond, Lock: processLock},
	)
	authRuntime := auth.NewCommandRuntime(
		store,
		applicationProfile.LoginURL,
		auth.NewBrowserOpener(runtime.GOOS, nil),
		auth.CommandRuntimeOptions{
			Refresher: tokenProvider,
			LoginFlow: auth.LoginFlowOptions{
				Lock: processLock,
				OnManualURL: func(loginURL string) {
					_, _ = fmt.Fprintf(stderr, "Open this URL to continue login:\n%s\n", loginURL)
				},
			},
		},
	)
	doctor.auth = authRuntime
	doctor.credentialAvailable = true
	doctor.credentialBackend = store.Backend()
	doctor.fileFallback = store.Backend() == "file"
	api, err := client.New(client.Config{
		BaseURL:        applicationProfile.APIBaseURL,
		HTTPClient:     httpClient,
		TokenProvider:  tokenProvider,
		RequestTimeout: 60 * time.Second,
		Metadata: client.Metadata{
			Version: version,
			OS:      runtime.GOOS,
			Arch:    runtime.GOARCH,
			Host:    host,
		},
		Uploader: upload.New(nil),
	})
	if err != nil {
		return cli.Runtime{}, err
	}
	return cli.Runtime{
		Profile:       applicationProfile.Name,
		WebBaseURL:    applicationProfile.WebBaseURL,
		Auth:          authRuntime,
		Projects:      api,
		Doctor:        doctor,
		Agent:         api,
		Conversations: api,
	}, nil
}

func credentialBackendForPlatform(platform string) string {
	switch platform {
	case "darwin":
		return "keychain"
	case "windows":
		return "credential-manager"
	case "linux":
		return "secret-service"
	default:
		return "unsupported"
	}
}

func normalizedHost(rawHost string) string {
	switch strings.ToLower(strings.TrimSpace(rawHost)) {
	case "codex":
		return "codex"
	case "claude", "claude-code":
		return "claude-code"
	default:
		return "unknown"
	}
}

func newHTTPClient() *http.Client {
	dialer := &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}
	return &http.Client{Transport: &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           dialer.DialContext,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          20,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ResponseHeaderTimeout: 30 * time.Second,
		ExpectContinueTimeout: time.Second,
	}}
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	os.Exit(runWithRuntimeFactory(ctx, os.Args[1:], os.Stdout, os.Stderr, newRuntime))
}
