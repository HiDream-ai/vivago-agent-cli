package main

import (
	"context"
	"strings"

	"github.com/HiDream-ai/vivago-agent-cli/internal/cli"
)

type doctorRuntime struct {
	version             string
	gitSHA              string
	channel             string
	profile             string
	platform            string
	architecture        string
	credentialBackend   string
	credentialAvailable bool
	fileFallback        bool
	auth                cli.AuthRuntime
}

func (runtime *doctorRuntime) Doctor(ctx context.Context) cli.DoctorReport {
	platformOK := supportedTarget(runtime.platform, runtime.architecture)
	buildOK := strings.TrimSpace(runtime.version) != "" &&
		strings.TrimSpace(runtime.gitSHA) != "" &&
		strings.TrimSpace(runtime.channel) != ""
	environmentOK := runtime.profile == "dev" || runtime.profile == "prod"

	loggedIn := false
	credentialsOK := runtime.credentialAvailable && runtime.auth != nil
	credentialMessage := ""
	if credentialsOK {
		status, err := runtime.auth.Status(ctx)
		if err != nil {
			credentialsOK = false
			credentialMessage = "credential status is unavailable"
		} else {
			loggedIn = status.LoggedIn
		}
	} else {
		credentialMessage = "operating-system credential store is unavailable"
	}

	checks := map[string]any{
		"build": map[string]any{
			"ok":      buildOK,
			"version": runtime.version,
			"git_sha": runtime.gitSHA,
			"channel": runtime.channel,
		},
		"platform": map[string]any{
			"ok":   platformOK,
			"os":   runtime.platform,
			"arch": runtime.architecture,
		},
		"environment": map[string]any{
			"ok":      environmentOK,
			"profile": runtime.profile,
			"target":  environmentTarget(runtime.profile),
		},
		"credentials": map[string]any{
			"ok":            credentialsOK,
			"backend":       runtime.credentialBackend,
			"file_fallback": runtime.fileFallback,
			"logged_in":     loggedIn,
			"message":       credentialMessage,
		},
	}
	return cli.DoctorReport{
		OK:     buildOK && platformOK && environmentOK && credentialsOK,
		Checks: checks,
	}
}

func supportedTarget(platform, architecture string) bool {
	if architecture != "arm64" && architecture != "amd64" {
		return false
	}
	return platform == "darwin" || platform == "linux" || platform == "windows"
}

func environmentTarget(profile string) string {
	if profile == "prod" {
		return "overseas-production"
	}
	if profile == "dev" {
		return "overseas-test"
	}
	return "unknown"
}
