package cli

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"io"
	"net/url"
	"strconv"
	"strings"

	"github.com/HiDream-ai/vivago-agent-cli/internal/artifact"
	"github.com/HiDream-ai/vivago-agent-cli/internal/attachment"
	"github.com/HiDream-ai/vivago-agent-cli/internal/auth"
	"github.com/HiDream-ai/vivago-agent-cli/internal/client"
)

const (
	exitUsage      = 2
	exitAuth       = 20
	exitBusiness   = 30
	exitDependency = 40
	exitNetwork    = 50
)

type BuildInfo struct {
	Version string
}

type envelope struct {
	OK    bool `json:"ok"`
	Data  any  `json:"data"`
	Error any  `json:"error"`
}

type AuthRuntime interface {
	Status(context.Context) (auth.Status, error)
	Login(context.Context) (auth.LoginResult, error)
	Logout(context.Context) error
	Refresh(context.Context) (auth.RefreshResult, error)
}

type Runtime struct {
	Profile       string
	WebBaseURL    string
	Auth          AuthRuntime
	Projects      ProjectRuntime
	Doctor        DoctorRuntime
	Agent         AgentRuntime
	Conversations ConversationRuntime
	Artifacts     ArtifactRuntime
}

type AgentRuntime interface {
	Ask(context.Context, string, string, string, bool, ...string) (*client.AgentStream, error)
	Resume(context.Context, string, string) (*client.AgentStream, error)
}

type ProjectRuntime interface {
	CreateProject(context.Context, string) (map[string]any, error)
	ListProjects(context.Context, int, int) (map[string]any, error)
	ListProjectAssets(context.Context, *int, int) (map[string]any, error)
}

type ConversationRuntime interface {
	Cancel(context.Context, string, string) (map[string]any, error)
	History(context.Context, string, int, int) (map[string]any, error)
}

type ArtifactRuntime interface {
	Download(context.Context, string, string, string) (artifact.DownloadResult, error)
	Preview(context.Context, string, string) (artifact.DownloadResult, error)
}

type DoctorReport struct {
	OK     bool           `json:"ok"`
	Checks map[string]any `json:"checks"`
}

type DoctorRuntime interface {
	Doctor(context.Context) DoctorReport
}

func Run(args []string, stdout, stderr io.Writer, build BuildInfo) int {
	return RunContext(context.Background(), args, stdout, stderr, build, Runtime{})
}

func RunContext(
	ctx context.Context,
	args []string,
	stdout, _ io.Writer,
	build BuildInfo,
	runtime Runtime,
) int {
	if len(args) >= 2 && args[0] == "--jsonl" {
		return runAgentCommand(ctx, args[1:], stdout, runtime.Agent)
	}
	if len(args) == 2 && args[0] == "--json" && args[1] == "version" {
		writeEnvelope(stdout, envelope{
			OK:   true,
			Data: map[string]string{"version": build.Version},
		})
		return 0
	}
	if len(args) == 2 && args[0] == "--json" && args[1] == "doctor" {
		if runtime.Doctor == nil {
			writeEnvelope(stdout, envelope{
				Error: map[string]string{
					"code":    "DEPENDENCY_MISSING",
					"message": "doctor runtime is unavailable",
				},
			})
			return exitDependency
		}
		report := runtime.Doctor.Doctor(ctx)
		if !report.OK {
			writeEnvelope(stdout, envelope{
				Data: report,
				Error: map[string]string{
					"code":    "DEPENDENCY_MISSING",
					"message": "one or more checks failed",
				},
			})
			return exitDependency
		}
		writeEnvelope(stdout, envelope{OK: true, Data: report})
		return 0
	}
	if len(args) >= 3 && args[0] == "--json" && args[1] == "artifact" {
		switch args[2] {
		case "url":
			flags := newFlagSet("artifact url")
			mediaType := flags.String("media-type", "", "image, video, or audio")
			contentID := flags.String("content-id", "", "artifact content ID or trusted URL")
			width := flags.Int("width", 0, "image width")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 {
				return writeInvalidArgument(stdout)
			}
			resolvedURL, err := artifact.ResolvePublicURL(*mediaType, *contentID, *width)
			if err != nil {
				return writeInvalidArgument(stdout)
			}
			writeEnvelope(stdout, envelope{
				OK:   true,
				Data: map[string]string{"url": resolvedURL},
			})
			return 0
		case "download":
			flags := newFlagSet("artifact download")
			mediaType := flags.String("media-type", "", "image, video, or audio")
			contentID := flags.String("content-id", "", "artifact content ID or trusted URL")
			outputPath := flags.String("output", "", "local output path")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 || strings.TrimSpace(*outputPath) == "" {
				return writeInvalidArgument(stdout)
			}
			if _, err := artifact.ResolvePublicURL(*mediaType, *contentID, 0); err != nil {
				return writeInvalidArgument(stdout)
			}
			artifactRuntime := runtime.Artifacts
			if artifactRuntime == nil {
				artifactRuntime = artifact.NewDownloader(nil)
			}
			result, err := artifactRuntime.Download(ctx, *mediaType, *contentID, *outputPath)
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		case "preview":
			flags := newFlagSet("artifact preview")
			mediaType := flags.String("media-type", "", "image, video, or audio")
			contentID := flags.String("content-id", "", "artifact content ID or trusted URL")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 {
				return writeInvalidArgument(stdout)
			}
			if _, err := artifact.ResolvePublicURL(*mediaType, *contentID, 0); err != nil {
				return writeInvalidArgument(stdout)
			}
			artifactRuntime := runtime.Artifacts
			if artifactRuntime == nil {
				artifactRuntime = artifact.NewDownloader(nil)
			}
			result, err := artifactRuntime.Preview(ctx, *mediaType, *contentID)
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		}
	}
	if len(args) == 3 && args[0] == "--json" && args[1] == "auth" {
		if runtime.Auth == nil {
			writeEnvelope(stdout, envelope{
				Error: map[string]string{
					"code":    "AUTH_DEPENDENCY_MISSING",
					"message": "authentication runtime is unavailable",
				},
			})
			return exitDependency
		}
		switch args[2] {
		case "status":
			status, err := runtime.Auth.Status(ctx)
			if err != nil {
				return writeAuthError(stdout)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: status})
			return 0
		case "login":
			result, err := runtime.Auth.Login(ctx)
			if err != nil {
				return writeAuthError(stdout)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		case "logout":
			if err := runtime.Auth.Logout(ctx); err != nil {
				return writeAuthError(stdout)
			}
			writeEnvelope(stdout, envelope{
				OK:   true,
				Data: map[string]bool{"logged_out": true},
			})
			return 0
		case "refresh":
			result, err := runtime.Auth.Refresh(ctx)
			if err != nil {
				return writeAuthOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		}
	}
	if len(args) >= 3 && args[0] == "--json" && args[1] == "project" {
		if args[2] == "link" {
			flags := newFlagSet("project link")
			projectID := flags.String("project-id", "", "project ID")
			conversationID := flags.String("conversation-id", "", "conversation ID")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 {
				return writeInvalidArgument(stdout)
			}
			*projectID = strings.TrimSpace(*projectID)
			*conversationID = strings.TrimSpace(*conversationID)
			deepLink, err := projectDeepLink(runtime.WebBaseURL, *projectID, *conversationID)
			if err != nil || strings.TrimSpace(runtime.Profile) == "" {
				return writeInvalidArgument(stdout)
			}
			writeEnvelope(stdout, envelope{
				OK: true,
				Data: map[string]string{
					"conversation_id": *conversationID,
					"deep_link":       deepLink,
					"profile":         strings.TrimSpace(runtime.Profile),
					"project_id":      *projectID,
				},
			})
			return 0
		}
		if runtime.Projects == nil {
			writeEnvelope(stdout, envelope{
				Error: map[string]string{
					"code":    "CLIENT_DEPENDENCY_MISSING",
					"message": "VivagoAgent client runtime is unavailable",
				},
			})
			return exitDependency
		}
		switch args[2] {
		case "create":
			flags := newFlagSet("project create")
			name := flags.String("name", "", "project name")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 || strings.TrimSpace(*name) == "" {
				return writeInvalidArgument(stdout)
			}
			result, err := runtime.Projects.CreateProject(ctx, strings.TrimSpace(*name))
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		case "list":
			flags := newFlagSet("project list")
			pageNumber := flags.Int("page-no", 0, "page number")
			pageSize := flags.Int("page-size", 20, "page size")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 ||
				*pageNumber < 0 || *pageSize < 1 || *pageSize > 100 {
				return writeInvalidArgument(stdout)
			}
			result, err := runtime.Projects.ListProjects(ctx, *pageNumber, *pageSize)
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		case "assets":
			flags := newFlagSet("project assets")
			offsetText := flags.String("offset", "", "asset pagination offset")
			pageSize := flags.Int("page-size", 20, "page size")
			if flags.Parse(args[3:]) != nil || flags.NArg() != 0 ||
				*pageSize < 1 || *pageSize > 100 {
				return writeInvalidArgument(stdout)
			}
			offset, ok := parseOptionalNonNegativeInt(*offsetText)
			if !ok {
				return writeInvalidArgument(stdout)
			}
			result, err := runtime.Projects.ListProjectAssets(ctx, offset, *pageSize)
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		}
	}
	if len(args) >= 2 && args[0] == "--json" && (args[1] == "cancel" || args[1] == "history") {
		if runtime.Conversations == nil {
			writeEnvelope(stdout, envelope{
				Error: map[string]string{
					"code":    "CLIENT_DEPENDENCY_MISSING",
					"message": "VivagoAgent client runtime is unavailable",
				},
			})
			return exitDependency
		}
		switch args[1] {
		case "cancel":
			flags := newFlagSet("cancel")
			conversationID := flags.String("conversation-id", "", "conversation ID")
			turnID := flags.String("turn-id", "", "turn ID")
			if flags.Parse(args[2:]) != nil || flags.NArg() != 0 {
				return writeInvalidArgument(stdout)
			}
			*conversationID = strings.TrimSpace(*conversationID)
			*turnID = strings.TrimSpace(*turnID)
			if *conversationID == "" || *turnID == "" {
				return writeInvalidArgument(stdout)
			}
			result, err := runtime.Conversations.Cancel(ctx, *conversationID, *turnID)
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		case "history":
			flags := newFlagSet("history")
			conversationID := flags.String("conversation-id", "", "conversation ID")
			pageNumber := flags.Int("page-no", 0, "page number")
			pageSize := flags.Int("page-size", 20, "page size")
			if flags.Parse(args[2:]) != nil || flags.NArg() != 0 {
				return writeInvalidArgument(stdout)
			}
			*conversationID = strings.TrimSpace(*conversationID)
			if *conversationID == "" || *pageNumber < 0 || *pageSize < 1 || *pageSize > 100 {
				return writeInvalidArgument(stdout)
			}
			result, err := runtime.Conversations.History(ctx, *conversationID, *pageNumber, *pageSize)
			if err != nil {
				return writeOperationError(stdout, err)
			}
			writeEnvelope(stdout, envelope{OK: true, Data: result})
			return 0
		}
	}
	return exitUsage
}

func projectDeepLink(baseURL, projectID, conversationID string) (string, error) {
	projectID = strings.TrimSpace(projectID)
	conversationID = strings.TrimSpace(conversationID)
	if projectID == "" || conversationID == "" {
		return "", errors.New("project and conversation identifiers are required")
	}
	parsed, err := url.Parse(strings.TrimSpace(baseURL))
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.User != nil ||
		parsed.RawQuery != "" || parsed.Fragment != "" {
		return "", errors.New("invalid web base URL")
	}
	parsed.Path = "/agent/new-chat"
	parsed.RawPath = ""
	query := url.Values{}
	query.Set("project_id", projectID)
	query.Set("conversation_id", conversationID)
	parsed.RawQuery = query.Encode()
	return parsed.String(), nil
}

func parseOptionalNonNegativeInt(raw string) (*int, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, true
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value < 0 {
		return nil, false
	}
	return &value, true
}

func runAgentCommand(
	ctx context.Context,
	args []string,
	stdout io.Writer,
	runtime AgentRuntime,
) int {
	if len(args) == 0 || (args[0] != "ask" && args[0] != "resume") {
		return exitUsage
	}
	if runtime == nil {
		writeEnvelope(stdout, envelope{
			Error: map[string]string{
				"code":    "CLIENT_DEPENDENCY_MISSING",
				"message": "VivagoAgent client runtime is unavailable",
			},
		})
		return exitDependency
	}

	var stream *client.AgentStream
	var err error
	switch args[0] {
	case "ask":
		flags := newFlagSet("ask")
		prompt := flags.String("prompt", "", "task prompt")
		projectID := flags.String("project-id", "", "project ID")
		conversationID := flags.String("conversation-id", "", "conversation ID")
		imageSearchEnabled := flags.Bool(
			"image-search",
			false,
			"enable online image and visual-reference search for this run",
		)
		var filePaths stringListFlag
		flags.Var(&filePaths, "file", "local attachment path; repeat for multiple files")
		if flags.Parse(args[1:]) != nil || flags.NArg() != 0 {
			return writeInvalidArgument(stdout)
		}
		*prompt = strings.TrimSpace(*prompt)
		*projectID = strings.TrimSpace(*projectID)
		*conversationID = strings.TrimSpace(*conversationID)
		if *prompt == "" || (*projectID == "") == (*conversationID == "") {
			return writeInvalidArgument(stdout)
		}
		stream, err = runtime.Ask(
			ctx,
			*prompt,
			*projectID,
			*conversationID,
			*imageSearchEnabled,
			filePaths...,
		)
	case "resume":
		flags := newFlagSet("resume")
		turnID := flags.String("turn-id", "", "turn ID")
		lastEventID := flags.String("last-event-id", "", "last received SSE event ID")
		if flags.Parse(args[1:]) != nil || flags.NArg() != 0 {
			return writeInvalidArgument(stdout)
		}
		*turnID = strings.TrimSpace(*turnID)
		*lastEventID = strings.TrimSpace(*lastEventID)
		if *turnID == "" {
			return writeInvalidArgument(stdout)
		}
		stream, err = runtime.Resume(ctx, *turnID, *lastEventID)
	}
	if err != nil {
		return writeOperationError(stdout, err)
	}
	if stream == nil || stream.Decoder == nil {
		return writeOperationError(stdout, errors.New("stream is unavailable"))
	}
	defer stream.Close()
	return EmitStream(stdout, Session{
		ConversationID: stream.ConversationID,
		TurnID:         stream.TurnID,
	}, stream.Decoder)
}

func newFlagSet(name string) *flag.FlagSet {
	flags := flag.NewFlagSet(name, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	return flags
}

type stringListFlag []string

func (values *stringListFlag) String() string {
	return strings.Join(*values, ",")
}

func (values *stringListFlag) Set(value string) error {
	*values = append(*values, value)
	return nil
}

func writeInvalidArgument(stdout io.Writer) int {
	writeEnvelope(stdout, envelope{
		Error: map[string]string{
			"code":    "INVALID_ARGUMENT",
			"message": "invalid command arguments",
		},
	})
	return exitUsage
}

func writeOperationError(stdout io.Writer, err error) int {
	if errors.Is(err, artifact.ErrInvalidArgument) || errors.Is(err, attachment.ErrInvalidArgument) {
		return writeInvalidArgument(stdout)
	}
	if errors.Is(err, auth.ErrLoginRequired) {
		writeEnvelope(stdout, envelope{
			Error: map[string]string{
				"code":    "AUTH_REQUIRED",
				"message": "login is required",
			},
		})
		return exitAuth
	}
	var httpError *client.HTTPError
	if errors.As(err, &httpError) &&
		httpError.StatusCode == 426 && httpError.Code == "CLI_VERSION_BLOCKED" {
		message := strings.TrimSpace(httpError.Message)
		if message == "" {
			message = "This Vivago Agent CLI version is no longer supported. Please upgrade and retry."
		}
		writeEnvelope(stdout, envelope{
			Error: map[string]string{
				"code":    "CLI_VERSION_BLOCKED",
				"message": message,
			},
		})
		return exitBusiness
	}
	if errors.As(err, &httpError) &&
		(httpError.StatusCode == 401 || httpError.StatusCode == 403) {
		writeEnvelope(stdout, envelope{
			Error: map[string]string{
				"code":    "AUTH_FAILED",
				"message": "authentication was rejected",
			},
		})
		return exitAuth
	}
	var businessError *client.BusinessError
	if errors.As(err, &businessError) {
		writeEnvelope(stdout, envelope{
			Error: map[string]any{
				"code":        "BUSINESS_ERROR",
				"server_code": businessError.Code,
				"message":     businessError.Message,
			},
		})
		return exitBusiness
	}
	writeEnvelope(stdout, envelope{
		Error: map[string]string{
			"code":    "TRANSPORT_ERROR",
			"message": "request failed",
		},
	})
	return exitNetwork
}

func writeAuthError(stdout io.Writer) int {
	writeEnvelope(stdout, envelope{
		Error: map[string]string{
			"code":    "AUTH_FAILED",
			"message": "authentication command failed",
		},
	})
	return exitAuth
}

func writeAuthOperationError(stdout io.Writer, err error) int {
	if errors.Is(err, auth.ErrLoginRequired) {
		writeEnvelope(stdout, envelope{
			Error: map[string]string{
				"code":    "AUTH_REQUIRED",
				"message": "login is required",
			},
		})
		return exitAuth
	}
	return writeAuthError(stdout)
}

func writeEnvelope(writer io.Writer, payload envelope) {
	_ = json.NewEncoder(writer).Encode(payload)
}
