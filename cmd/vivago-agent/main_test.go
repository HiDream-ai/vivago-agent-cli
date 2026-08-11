package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"testing"

	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
	"github.com/HiDream-ai/vivago-agent-cli/internal/cli"
	"github.com/HiDream-ai/vivago-agent-cli/internal/config"
)

func TestRunDelegatesVersionCommandToCLI(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	exitCode := run([]string{"--json", "version"}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("exit code = %d, want 0", exitCode)
	}
	var payload struct {
		Data struct {
			Version string `json:"version"`
		} `json:"data"`
	}
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil {
		t.Fatalf("stdout is not JSON: %v", err)
	}
	if payload.Data.Version != "dev" {
		t.Fatalf("version = %q, want dev", payload.Data.Version)
	}
	if stderr.String() != "" {
		t.Fatalf("stderr = %q, want empty", stderr.String())
	}
}

func TestRunAuthStatusInitializesAuthenticationRuntime(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	factoryCalls := 0
	runtime := &mainTestAuthRuntime{status: auth.Status{LoggedIn: true, Backend: "keychain"}}

	exitCode := runWithAuthFactory(
		context.Background(),
		[]string{"--json", "auth", "status"},
		&stdout,
		&stderr,
		func(context.Context, io.Writer) (cli.AuthRuntime, error) {
			factoryCalls++
			return runtime, nil
		},
	)

	if exitCode != 0 || factoryCalls != 1 {
		t.Fatalf("exit code = %d, factory calls = %d, stdout = %s", exitCode, factoryCalls, stdout.String())
	}
	if !bytes.Contains(stdout.Bytes(), []byte(`"backend":"keychain"`)) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestRunVersionDoesNotInitializeAuthenticationRuntime(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	factoryCalls := 0

	exitCode := runWithAuthFactory(
		context.Background(),
		[]string{"--json", "version"},
		&stdout,
		&stderr,
		func(context.Context, io.Writer) (cli.AuthRuntime, error) {
			factoryCalls++
			return nil, errors.New("unexpected authentication initialization")
		},
	)

	if exitCode != 0 || factoryCalls != 0 {
		t.Fatalf("exit code = %d, factory calls = %d", exitCode, factoryCalls)
	}
}

func TestArtifactURLDoesNotInitializeAuthenticationRuntime(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	factoryCalls := 0

	exitCode := runWithRuntimeFactory(
		context.Background(),
		[]string{"--json", "artifact", "url", "--media-type", "image", "--content-id", "p-cat"},
		&stdout,
		&stderr,
		func(context.Context, io.Writer) (cli.Runtime, error) {
			factoryCalls++
			return cli.Runtime{}, errors.New("authentication must not initialize")
		},
	)

	if exitCode != 0 || factoryCalls != 0 {
		t.Fatalf("exit = %d, factory calls = %d, stdout = %s", exitCode, factoryCalls, stdout.String())
	}
}

func TestRunProjectCommandInitializesClientRuntime(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	factoryCalls := 0
	projects := &mainTestProjectRuntime{}

	exitCode := runWithRuntimeFactory(
		context.Background(),
		[]string{"--json", "project", "create", "--name", "Codex task"},
		&stdout,
		&stderr,
		func(context.Context, io.Writer) (cli.Runtime, error) {
			factoryCalls++
			return cli.Runtime{Projects: projects}, nil
		},
	)

	if exitCode != 0 || factoryCalls != 1 || projects.createdName != "Codex task" {
		t.Fatalf(
			"exit = %d, factory calls = %d, project = %q, stdout = %s",
			exitCode,
			factoryCalls,
			projects.createdName,
			stdout.String(),
		)
	}
}

func TestRunProjectLinkUsesCompiledProfileWithoutInitializingClientRuntime(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	factoryCalls := 0

	exitCode := runWithRuntimeFactory(
		context.Background(),
		[]string{
			"--json", "project", "link",
			"--project-id", "project-1",
			"--conversation-id", "conversation-1",
		},
		&stdout,
		&stderr,
		func(context.Context, io.Writer) (cli.Runtime, error) {
			factoryCalls++
			return cli.Runtime{}, errors.New("client runtime must not initialize")
		},
	)

	if exitCode != 0 || factoryCalls != 0 {
		t.Fatalf("exit = %d, factory calls = %d, stdout = %s", exitCode, factoryCalls, stdout.String())
	}
	profile := config.Current()
	if !bytes.Contains(stdout.Bytes(), []byte(`"deep_link":"`+profile.WebBaseURL+`/agent/new-chat?`)) ||
		!bytes.Contains(stdout.Bytes(), []byte(`"profile":"`+profile.Name+`"`)) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestRunJSONLCommandInitializesClientRuntime(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	factoryCalls := 0

	exitCode := runWithRuntimeFactory(
		context.Background(),
		[]string{"--jsonl", "ask", "--prompt", "hello", "--project-id", "p-1"},
		&stdout,
		&stderr,
		func(context.Context, io.Writer) (cli.Runtime, error) {
			factoryCalls++
			return cli.Runtime{}, errors.New("test runtime unavailable")
		},
	)

	if factoryCalls != 1 {
		t.Fatalf("factory calls = %d, want 1", factoryCalls)
	}
	if exitCode != 40 || !bytes.Contains(stdout.Bytes(), []byte(`"code":"CLIENT_DEPENDENCY_MISSING"`)) {
		t.Fatalf("exit = %d, stdout = %s", exitCode, stdout.String())
	}
}

func TestControlCommandsRequireClientRuntime(t *testing.T) {
	for _, args := range [][]string{
		{"--json", "cancel", "--conversation-id", "c-1", "--turn-id", "t-1"},
		{"--json", "history", "--conversation-id", "c-1"},
		{"--json", "project", "assets"},
	} {
		if !requiresRuntime(args) {
			t.Fatalf("requiresRuntime(%v) = false", args)
		}
	}
}

func TestDoctorRuntimeReportsBuildPlatformAndCredentialState(t *testing.T) {
	runtime := &doctorRuntime{
		version:             "0.3.0-dev",
		gitSHA:              "abc123",
		channel:             "dev",
		profile:             "dev",
		platform:            "linux",
		architecture:        "arm64",
		credentialBackend:   "file",
		credentialAvailable: true,
		fileFallback:        true,
		auth: &mainTestAuthRuntime{status: auth.Status{
			LoggedIn: false,
			Backend:  "file",
		}},
	}

	report := runtime.Doctor(context.Background())
	if !report.OK {
		t.Fatalf("report = %#v", report)
	}
	credentials, ok := report.Checks["credentials"].(map[string]any)
	if !ok || credentials["backend"] != "file" || credentials["file_fallback"] != true {
		t.Fatalf("credentials check = %#v", report.Checks["credentials"])
	}
	if _, exists := credentials["ticket"]; exists {
		t.Fatal("doctor report contains ticket")
	}
}

type mainTestAuthRuntime struct {
	status auth.Status
}

func (runtime *mainTestAuthRuntime) Status(context.Context) (auth.Status, error) {
	return runtime.status, nil
}

func (*mainTestAuthRuntime) Login(context.Context) (auth.LoginResult, error) {
	return auth.LoginResult{}, nil
}

func (*mainTestAuthRuntime) Logout(context.Context) error {
	return nil
}

func (*mainTestAuthRuntime) Refresh(context.Context) (auth.RefreshResult, error) {
	return auth.RefreshResult{Refreshed: true, Backend: "keychain"}, nil
}

type mainTestProjectRuntime struct {
	createdName string
}

func (runtime *mainTestProjectRuntime) CreateProject(_ context.Context, name string) (map[string]any, error) {
	runtime.createdName = name
	return map[string]any{"code": 0}, nil
}

func (*mainTestProjectRuntime) ListProjects(context.Context, int, int) (map[string]any, error) {
	return map[string]any{"code": 0}, nil
}

func (*mainTestProjectRuntime) ListProjectAssets(context.Context, *int, int) (map[string]any, error) {
	return map[string]any{"code": 0}, nil
}
