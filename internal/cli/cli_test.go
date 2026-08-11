package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"reflect"
	"strings"
	"testing"

	"github.com/HiDream-ai/vivago-agent-cli/internal/artifact"
	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
	"github.com/HiDream-ai/vivago-agent-cli/internal/client"
	"github.com/HiDream-ai/vivago-agent-cli/internal/sse"
)

func TestVersionJSONUsesStableEnvelope(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	exitCode := Run([]string{"--json", "version"}, &stdout, &stderr, BuildInfo{
		Version: "0.3.0-dev",
	})

	if exitCode != 0 {
		t.Fatalf("exit code = %d, want 0", exitCode)
	}
	if stderr.String() != "" {
		t.Fatalf("stderr = %q, want empty", stderr.String())
	}

	var payload struct {
		OK   bool `json:"ok"`
		Data struct {
			Version string `json:"version"`
		} `json:"data"`
		Error any `json:"error"`
	}
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil {
		t.Fatalf("stdout is not one JSON object: %v\n%s", err, stdout.String())
	}
	if !payload.OK {
		t.Fatal("ok = false, want true")
	}
	if payload.Data.Version != "0.3.0-dev" {
		t.Fatalf("version = %q, want %q", payload.Data.Version, "0.3.0-dev")
	}
	if payload.Error != nil {
		t.Fatalf("error = %#v, want nil", payload.Error)
	}
}

func TestAuthStatusJSONDoesNotExposeCredentials(t *testing.T) {
	runtime := &fakeAuthRuntime{status: auth.Status{
		LoggedIn:     true,
		Backend:      "keychain",
		NeedsRefresh: false,
	}}
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "auth", "status"},
		&stdout,
		&stderr,
		BuildInfo{Version: "0.3.0-dev"},
		Runtime{Auth: runtime},
	)

	if exitCode != 0 {
		t.Fatalf("exit code = %d, want 0", exitCode)
	}
	if stderr.String() != "" {
		t.Fatalf("stderr = %q", stderr.String())
	}
	if bytes.Contains(stdout.Bytes(), []byte("ticket")) || bytes.Contains(stdout.Bytes(), []byte("refresh_token")) {
		t.Fatalf("stdout contains credential fields: %s", stdout.String())
	}
	var payload struct {
		OK   bool        `json:"ok"`
		Data auth.Status `json:"data"`
	}
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil {
		t.Fatalf("stdout is not JSON: %v", err)
	}
	if !payload.OK || !payload.Data.LoggedIn || payload.Data.Backend != "keychain" {
		t.Fatalf("payload = %#v", payload)
	}
}

func TestAuthLoginAndLogoutJSONUseRuntime(t *testing.T) {
	runtime := &fakeAuthRuntime{loginResult: auth.LoginResult{Backend: "credential-manager"}}
	commands := []struct {
		name string
		args []string
	}{
		{name: "login", args: []string{"--json", "auth", "login"}},
		{name: "logout", args: []string{"--json", "auth", "logout"}},
	}
	for _, testCase := range commands {
		t.Run(testCase.name, func(t *testing.T) {
			var stdout bytes.Buffer
			var stderr bytes.Buffer
			exitCode := RunContext(
				context.Background(),
				testCase.args,
				&stdout,
				&stderr,
				BuildInfo{Version: "0.3.0-dev"},
				Runtime{Auth: runtime},
			)
			if exitCode != 0 {
				t.Fatalf("exit code = %d, want 0: %s", exitCode, stdout.String())
			}
			if stderr.String() != "" {
				t.Fatalf("stderr = %q", stderr.String())
			}
			var payload struct {
				OK bool `json:"ok"`
			}
			if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil || !payload.OK {
				t.Fatalf("stdout = %q, err = %v", stdout.String(), err)
			}
		})
	}
	if runtime.loginCalls != 1 || runtime.logoutCalls != 1 {
		t.Fatalf("calls = login %d, logout %d", runtime.loginCalls, runtime.logoutCalls)
	}
}

func TestAuthRefreshJSONUsesRuntimeWithoutExposingCredentials(t *testing.T) {
	runtime := &fakeAuthRuntime{refreshResult: auth.RefreshResult{
		Refreshed: true,
		Backend:   "keychain",
	}}
	var stdout bytes.Buffer

	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "auth", "refresh"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "0.3.0-dev"},
		Runtime{Auth: runtime, AllowManualAuthRefresh: true},
	)

	if exitCode != 0 {
		t.Fatalf("exit code = %d, want 0: %s", exitCode, stdout.String())
	}
	if runtime.refreshCalls != 1 {
		t.Fatalf("refresh calls = %d, want 1", runtime.refreshCalls)
	}
	if strings.Contains(stdout.String(), "ticket") || strings.Contains(stdout.String(), "refresh_token") {
		t.Fatalf("stdout contains credential fields: %s", stdout.String())
	}
	if stdout.String() != "{\"ok\":true,\"data\":{\"refreshed\":true,\"backend\":\"keychain\"},\"error\":null}\n" {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestAuthRefreshIsUnavailableWithoutCallingRuntimeInProduction(t *testing.T) {
	runtime := &fakeAuthRuntime{}
	var stdout bytes.Buffer

	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "auth", "refresh"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "0.3.0"},
		Runtime{Auth: runtime, AllowManualAuthRefresh: false},
	)

	if exitCode != exitUsage {
		t.Fatalf("exit code = %d, want %d", exitCode, exitUsage)
	}
	if runtime.refreshCalls != 0 {
		t.Fatalf("refresh calls = %d, want 0", runtime.refreshCalls)
	}
	if !strings.Contains(stdout.String(), `"code":"COMMAND_UNAVAILABLE"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestAuthRefreshMapsMissingCredentialsWithoutExposingRuntimeError(t *testing.T) {
	runtime := &fakeAuthRuntime{refreshErr: auth.ErrLoginRequired}
	var stdout bytes.Buffer

	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "auth", "refresh"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "0.3.0-dev"},
		Runtime{Auth: runtime, AllowManualAuthRefresh: true},
	)

	if exitCode != exitAuth {
		t.Fatalf("exit code = %d, want %d", exitCode, exitAuth)
	}
	if !strings.Contains(stdout.String(), `"code":"AUTH_REQUIRED"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestProjectCreateAndListJSONUseRuntime(t *testing.T) {
	projects := &fakeProjectRuntime{}
	commands := []struct {
		name string
		args []string
	}{
		{
			name: "create",
			args: []string{"--json", "project", "create", "--name", "Codex task"},
		},
		{
			name: "list",
			args: []string{"--json", "project", "list", "--page-no", "2", "--page-size", "10"},
		},
	}
	for _, testCase := range commands {
		t.Run(testCase.name, func(t *testing.T) {
			var stdout bytes.Buffer
			var stderr bytes.Buffer
			exitCode := RunContext(
				context.Background(),
				testCase.args,
				&stdout,
				&stderr,
				BuildInfo{Version: "0.3.0-dev"},
				Runtime{Projects: projects},
			)
			if exitCode != 0 {
				t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
			}
			var payload struct {
				OK bool `json:"ok"`
			}
			if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil || !payload.OK {
				t.Fatalf("stdout = %q, err = %v", stdout.String(), err)
			}
		})
	}
	if projects.createdName != "Codex task" {
		t.Fatalf("created name = %q", projects.createdName)
	}
	if projects.pageNumber != 2 || projects.pageSize != 10 {
		t.Fatalf("list pagination = %d / %d", projects.pageNumber, projects.pageSize)
	}
}

func TestProjectLinkUsesBuildProfileWithoutCallingProjectRuntime(t *testing.T) {
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--json",
			"project",
			"link",
			"--project-id",
			"project/with space",
			"--conversation-id",
			"conversation?value",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "0.3.0-dev"},
		Runtime{
			Profile:    "dev",
			WebBaseURL: "https://dev.vivago.ai",
		},
	)

	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	want := "{\"ok\":true,\"data\":{" +
		"\"conversation_id\":\"conversation?value\"," +
		"\"deep_link\":\"https://dev.vivago.ai/agent/new-chat?conversation_id=conversation%3Fvalue\\u0026project_id=project%2Fwith+space\"," +
		"\"profile\":\"dev\"," +
		"\"project_id\":\"project/with space\"},\"error\":null}\n"
	if stdout.String() != want {
		t.Fatalf("stdout = %s, want %s", stdout.String(), want)
	}
}

func TestProjectLinkRejectsMissingIdentifiersOrRuntimeProfile(t *testing.T) {
	testCases := []struct {
		name    string
		args    []string
		runtime Runtime
	}{
		{
			name: "missing conversation",
			args: []string{"--json", "project", "link", "--project-id", "project"},
			runtime: Runtime{
				Profile:    "dev",
				WebBaseURL: "https://dev.vivago.ai",
			},
		},
		{
			name: "missing profile",
			args: []string{
				"--json", "project", "link",
				"--project-id", "project",
				"--conversation-id", "conversation",
			},
			runtime: Runtime{},
		},
	}
	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			var stdout bytes.Buffer
			exitCode := RunContext(
				context.Background(),
				testCase.args,
				&stdout,
				&bytes.Buffer{},
				BuildInfo{},
				testCase.runtime,
			)
			if exitCode != exitUsage || !strings.Contains(stdout.String(), `"code":"INVALID_ARGUMENT"`) {
				t.Fatalf("exit = %d, stdout = %s", exitCode, stdout.String())
			}
		})
	}
}

func TestProjectAssetsJSONUsesOptionalOffset(t *testing.T) {
	projects := &fakeProjectRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "project", "assets", "--offset", "123456", "--page-size", "50"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Projects: projects},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if projects.assetOffset == nil || *projects.assetOffset != 123456 || projects.assetPageSize != 50 {
		t.Fatalf("assets arguments = %#v / %d", projects.assetOffset, projects.assetPageSize)
	}
}

func TestCancelAndHistoryJSONUseConversationRuntime(t *testing.T) {
	conversations := &fakeConversationRuntime{}
	commands := [][]string{
		{"--json", "cancel", "--conversation-id", "c-1", "--turn-id", "t-1"},
		{"--json", "history", "--conversation-id", "c-1", "--page-no", "2", "--page-size", "10"},
	}
	for _, command := range commands {
		var stdout bytes.Buffer
		exitCode := RunContext(
			context.Background(),
			command,
			&stdout,
			&bytes.Buffer{},
			BuildInfo{Version: "dev"},
			Runtime{Conversations: conversations},
		)
		if exitCode != 0 {
			t.Fatalf("command %v exit = %d, stdout = %s", command, exitCode, stdout.String())
		}
	}
	if conversations.cancelConversationID != "c-1" || conversations.cancelTurnID != "t-1" {
		t.Fatalf("cancel = %#v", conversations)
	}
	if conversations.historyConversationID != "c-1" ||
		conversations.pageNumber != 2 || conversations.pageSize != 10 {
		t.Fatalf("history = %#v", conversations)
	}
}

func TestControlCommandsRejectInvalidArgumentsBeforeRuntime(t *testing.T) {
	projects := &fakeProjectRuntime{}
	conversations := &fakeConversationRuntime{}
	commands := []struct {
		args    []string
		runtime Runtime
	}{
		{
			args:    []string{"--json", "project", "assets", "--offset", "not-an-int"},
			runtime: Runtime{Projects: projects},
		},
		{
			args:    []string{"--json", "cancel", "--conversation-id", "c-1"},
			runtime: Runtime{Conversations: conversations},
		},
		{
			args:    []string{"--json", "history", "--conversation-id", "c-1", "--page-size", "0"},
			runtime: Runtime{Conversations: conversations},
		},
	}
	for _, testCase := range commands {
		var stdout bytes.Buffer
		if exitCode := RunContext(
			context.Background(), testCase.args, &stdout, &bytes.Buffer{},
			BuildInfo{Version: "dev"}, testCase.runtime,
		); exitCode != 2 {
			t.Fatalf("command %v exit = %d, stdout = %s", testCase.args, exitCode, stdout.String())
		}
	}
	if projects.assetCalls != 0 || conversations.cancelCalls != 0 || conversations.historyCalls != 0 {
		t.Fatalf("runtime was called: projects=%#v conversations=%#v", projects, conversations)
	}
}

func TestProjectListRejectsInvalidPaginationBeforeRuntime(t *testing.T) {
	projects := &fakeProjectRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "project", "list", "--page-size", "0"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Projects: projects},
	)
	if exitCode != 2 {
		t.Fatalf("exit code = %d, want 2", exitCode)
	}
	if projects.listCalls != 0 {
		t.Fatalf("runtime called %d times", projects.listCalls)
	}
	if !bytes.Contains(stdout.Bytes(), []byte(`"code":"INVALID_ARGUMENT"`)) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestProjectCommandMapsUnauthorizedHTTPToAuthFailure(t *testing.T) {
	projects := &fakeProjectRuntime{err: &client.HTTPError{StatusCode: 401}}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "project", "list"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Projects: projects},
	)
	if exitCode != 20 {
		t.Fatalf("exit code = %d, want 20", exitCode)
	}
	if !bytes.Contains(stdout.Bytes(), []byte(`"code":"AUTH_FAILED"`)) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestDoctorJSONReturnsChecksWithoutSecrets(t *testing.T) {
	doctor := &fakeDoctorRuntime{report: DoctorReport{
		OK: true,
		Checks: map[string]any{
			"platform":    map[string]any{"ok": true, "os": "darwin", "arch": "arm64"},
			"credentials": map[string]any{"ok": true, "backend": "keychain", "logged_in": false},
		},
	}}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "doctor"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Doctor: doctor},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if bytes.Contains(stdout.Bytes(), []byte("ticket")) || bytes.Contains(stdout.Bytes(), []byte("refresh_token")) {
		t.Fatalf("doctor leaked credentials: %s", stdout.String())
	}
	if !bytes.Contains(stdout.Bytes(), []byte(`"backend":"keychain"`)) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestDoctorReturnsDependencyExitWhenCheckFails(t *testing.T) {
	doctor := &fakeDoctorRuntime{report: DoctorReport{
		OK: false,
		Checks: map[string]any{
			"credentials": map[string]any{"ok": false, "backend": "keychain"},
		},
	}}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--json", "doctor"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Doctor: doctor},
	)
	if exitCode != 40 {
		t.Fatalf("exit code = %d, want 40", exitCode)
	}
	if !bytes.Contains(stdout.Bytes(), []byte(`"code":"DEPENDENCY_MISSING"`)) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestArtifactURLJSONResolvesWithoutRuntime(t *testing.T) {
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--json", "artifact", "url", "--media-type", "image",
			"--content-id", "p-cat", "--width", "512",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if !strings.Contains(stdout.String(), `"url":"https://storage.vivago.ai/image/p-cat.jpg?width=512"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestArtifactURLJSONRejectsUntrustedURL(t *testing.T) {
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--json", "artifact", "url", "--media-type", "image",
			"--content-id", "https://evil.test/cat.png",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{},
	)
	if exitCode != 2 || !strings.Contains(stdout.String(), `"code":"INVALID_ARGUMENT"`) {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
}

func TestArtifactDownloadAndPreviewJSONUseArtifactRuntime(t *testing.T) {
	artifacts := &fakeArtifactRuntime{}
	commands := [][]string{
		{
			"--json", "artifact", "download", "--media-type", "video",
			"--content-id", "v-1", "--output", "/tmp/video.mp4",
		},
		{
			"--json", "artifact", "preview", "--media-type", "image",
			"--content-id", "p-1",
		},
	}
	for _, command := range commands {
		var stdout bytes.Buffer
		exitCode := RunContext(
			context.Background(), command, &stdout, &bytes.Buffer{},
			BuildInfo{Version: "dev"}, Runtime{Artifacts: artifacts},
		)
		if exitCode != 0 || !strings.Contains(stdout.String(), `"path":"/tmp/result"`) {
			t.Fatalf("command %v exit = %d, stdout = %s", command, exitCode, stdout.String())
		}
	}
	if artifacts.downloadMediaType != "video" || artifacts.downloadContentID != "v-1" ||
		artifacts.outputPath != "/tmp/video.mp4" {
		t.Fatalf("download arguments = %#v", artifacts)
	}
	if artifacts.previewMediaType != "image" || artifacts.previewContentID != "p-1" {
		t.Fatalf("preview arguments = %#v", artifacts)
	}
}

func TestArtifactArgumentFailureUsesUsageExit(t *testing.T) {
	artifacts := &fakeArtifactRuntime{err: errors.Join(artifact.ErrInvalidArgument, errors.New("exists"))}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--json", "artifact", "download", "--media-type", "image",
			"--content-id", "p-1", "--output", "/tmp/existing.jpg",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Artifacts: artifacts},
	)
	if exitCode != 2 || !strings.Contains(stdout.String(), `"code":"INVALID_ARGUMENT"`) {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
}

func TestAskJSONLStreamsSessionAndEvents(t *testing.T) {
	agent := &fakeAgentRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--jsonl", "ask", "--prompt", "Make a cat", "--project-id", "p-1"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Agent: agent},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if agent.prompt != "Make a cat" || agent.projectID != "p-1" || agent.conversationID != "" {
		t.Fatalf("ask arguments = %#v", agent)
	}
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	if len(lines) != 3 {
		t.Fatalf("JSONL lines = %d\n%s", len(lines), stdout.String())
	}
	if !strings.Contains(lines[0], `"type":"session"`) ||
		!strings.Contains(lines[0], `"conversation_id":"c-1"`) ||
		!strings.Contains(lines[0], `"turn_id":"t-1"`) {
		t.Fatalf("session line = %s", lines[0])
	}
	if !strings.Contains(lines[2], "RUN_FINISHED") {
		t.Fatalf("terminal line = %s", lines[2])
	}
}

func TestAskJSONLAcceptsRepeatableAttachmentPaths(t *testing.T) {
	agent := &fakeAgentRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--jsonl", "ask", "--prompt", "Use these", "--project-id", "p-1",
			"--file", "/tmp/cat.png", "--file", "/tmp/voice.mp3",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Agent: agent},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if !reflect.DeepEqual(agent.filePaths, []string{"/tmp/cat.png", "/tmp/voice.mp3"}) {
		t.Fatalf("file paths = %#v", agent.filePaths)
	}
}

func TestAskJSONLEnablesImageSearchForNewRun(t *testing.T) {
	agent := &fakeAgentRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--jsonl", "ask", "--prompt", "Find visual references", "--project-id", "p-1",
			"--image-search",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Agent: agent},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if !agent.imageSearchEnabled {
		t.Fatal("image search was not enabled")
	}
}

func TestResumeJSONLUsesSameTurnAndCursor(t *testing.T) {
	agent := &fakeAgentRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{"--jsonl", "resume", "--turn-id", "t-original", "--last-event-id", "42-0"},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Agent: agent},
	)
	if exitCode != 0 {
		t.Fatalf("exit code = %d, stdout = %s", exitCode, stdout.String())
	}
	if agent.turnID != "t-original" || agent.lastEventID != "42-0" {
		t.Fatalf("resume arguments = %#v", agent)
	}
	if agent.askCalls != 0 || agent.resumeCalls != 1 {
		t.Fatalf("calls = ask %d, resume %d", agent.askCalls, agent.resumeCalls)
	}
}

func TestAskJSONLRejectsAmbiguousRoutingBeforeRuntime(t *testing.T) {
	agent := &fakeAgentRuntime{}
	var stdout bytes.Buffer
	exitCode := RunContext(
		context.Background(),
		[]string{
			"--jsonl", "ask", "--prompt", "hello",
			"--project-id", "p-1", "--conversation-id", "c-1",
		},
		&stdout,
		&bytes.Buffer{},
		BuildInfo{Version: "dev"},
		Runtime{Agent: agent},
	)
	if exitCode != 2 {
		t.Fatalf("exit code = %d, want 2", exitCode)
	}
	if agent.askCalls != 0 {
		t.Fatalf("ask calls = %d", agent.askCalls)
	}
	if !strings.Contains(stdout.String(), `"code":"INVALID_ARGUMENT"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

type fakeAuthRuntime struct {
	status        auth.Status
	loginResult   auth.LoginResult
	refreshResult auth.RefreshResult
	refreshErr    error
	loginCalls    int
	logoutCalls   int
	refreshCalls  int
}

func (runtime *fakeAuthRuntime) Status(context.Context) (auth.Status, error) {
	return runtime.status, nil
}

func (runtime *fakeAuthRuntime) Login(context.Context) (auth.LoginResult, error) {
	runtime.loginCalls++
	return runtime.loginResult, nil
}

func (runtime *fakeAuthRuntime) Logout(context.Context) error {
	runtime.logoutCalls++
	return nil
}

func (runtime *fakeAuthRuntime) Refresh(context.Context) (auth.RefreshResult, error) {
	runtime.refreshCalls++
	return runtime.refreshResult, runtime.refreshErr
}

type fakeProjectRuntime struct {
	createdName   string
	pageNumber    int
	pageSize      int
	listCalls     int
	assetOffset   *int
	assetPageSize int
	assetCalls    int
	err           error
}

func (runtime *fakeProjectRuntime) CreateProject(_ context.Context, name string) (map[string]any, error) {
	runtime.createdName = name
	return map[string]any{"code": 0, "data": map[string]any{"project_id": "p-1"}}, runtime.err
}

func (runtime *fakeProjectRuntime) ListProjects(_ context.Context, pageNumber, pageSize int) (map[string]any, error) {
	runtime.pageNumber = pageNumber
	runtime.pageSize = pageSize
	runtime.listCalls++
	return map[string]any{"code": 0, "data": map[string]any{"projects": []any{}}}, runtime.err
}

func (runtime *fakeProjectRuntime) ListProjectAssets(
	_ context.Context,
	offset *int,
	pageSize int,
) (map[string]any, error) {
	runtime.assetOffset = offset
	runtime.assetPageSize = pageSize
	runtime.assetCalls++
	return map[string]any{"code": 0, "data": map[string]any{"assets": []any{}}}, runtime.err
}

type fakeDoctorRuntime struct {
	report DoctorReport
}

func (runtime *fakeDoctorRuntime) Doctor(context.Context) DoctorReport {
	return runtime.report
}

type fakeAgentRuntime struct {
	prompt             string
	projectID          string
	conversationID     string
	turnID             string
	lastEventID        string
	filePaths          []string
	imageSearchEnabled bool
	askCalls           int
	resumeCalls        int
	err                error
}

func (runtime *fakeAgentRuntime) Ask(
	_ context.Context,
	prompt, projectID, conversationID string,
	imageSearchEnabled bool,
	filePaths ...string,
) (*client.AgentStream, error) {
	runtime.askCalls++
	runtime.prompt = prompt
	runtime.projectID = projectID
	runtime.conversationID = conversationID
	runtime.imageSearchEnabled = imageSearchEnabled
	runtime.filePaths = append([]string(nil), filePaths...)
	return fakeCompletedStream(), runtime.err
}

func (runtime *fakeAgentRuntime) Resume(
	_ context.Context,
	turnID, lastEventID string,
) (*client.AgentStream, error) {
	runtime.resumeCalls++
	runtime.turnID = turnID
	runtime.lastEventID = lastEventID
	return fakeCompletedStream(), runtime.err
}

func fakeCompletedStream() *client.AgentStream {
	return &client.AgentStream{
		ConversationID: "c-1",
		TurnID:         "t-1",
		Decoder: sse.NewDecoder(strings.NewReader(
			"id: 1-0\ndata: {\"type\":\"RUN_STARTED\"}\n\n" +
				"id: 2-0\ndata: {\"type\":\"RUN_FINISHED\"}\n\n",
		)),
	}
}

type fakeConversationRuntime struct {
	cancelConversationID  string
	cancelTurnID          string
	historyConversationID string
	pageNumber            int
	pageSize              int
	cancelCalls           int
	historyCalls          int
	err                   error
}

type fakeArtifactRuntime struct {
	downloadMediaType string
	downloadContentID string
	outputPath        string
	previewMediaType  string
	previewContentID  string
	err               error
}

func (runtime *fakeArtifactRuntime) Download(
	_ context.Context,
	mediaType, contentID, outputPath string,
) (artifact.DownloadResult, error) {
	runtime.downloadMediaType = mediaType
	runtime.downloadContentID = contentID
	runtime.outputPath = outputPath
	return artifact.DownloadResult{Path: "/tmp/result", Bytes: 10, ContentType: "video/mp4"}, runtime.err
}

func (runtime *fakeArtifactRuntime) Preview(
	_ context.Context,
	mediaType, contentID string,
) (artifact.DownloadResult, error) {
	runtime.previewMediaType = mediaType
	runtime.previewContentID = contentID
	return artifact.DownloadResult{Path: "/tmp/result", Bytes: 10, ContentType: "image/jpeg"}, runtime.err
}

func (runtime *fakeConversationRuntime) Cancel(
	_ context.Context,
	conversationID, turnID string,
) (map[string]any, error) {
	runtime.cancelCalls++
	runtime.cancelConversationID = conversationID
	runtime.cancelTurnID = turnID
	return map[string]any{"code": 0, "data": map[string]any{}}, runtime.err
}

func (runtime *fakeConversationRuntime) History(
	_ context.Context,
	conversationID string,
	pageNumber, pageSize int,
) (map[string]any, error) {
	runtime.historyCalls++
	runtime.historyConversationID = conversationID
	runtime.pageNumber = pageNumber
	runtime.pageSize = pageSize
	return map[string]any{"code": 0, "data": map[string]any{}}, runtime.err
}
