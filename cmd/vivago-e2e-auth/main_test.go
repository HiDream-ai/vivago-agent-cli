package main

import (
	"bytes"
	"context"
	"testing"
)

func TestValidProfileAcceptsOnlyCompiledProfiles(t *testing.T) {
	for _, profile := range []string{"dev", "prod"} {
		if !validProfile(profile) {
			t.Fatalf("valid profile %q was rejected", profile)
		}
	}
	for _, profile := range []string{"", "staging", "production", "DEV"} {
		if validProfile(profile) {
			t.Fatalf("unsupported profile %q was accepted", profile)
		}
	}
}

func TestSubcommandsRejectUnsupportedProfileBeforeCredentialAccess(t *testing.T) {
	for _, args := range [][]string{
		{"seed", "--profile", "staging"},
		{"clear", "--profile", "staging"},
		{
			"publish",
			"--profile",
			"staging",
			"--repo",
			"HiDream-ai/vivago-agent-cli",
			"--environment",
			"production-beta",
		},
	} {
		var stdout bytes.Buffer
		if err := run(context.Background(), args, &stdout); err == nil {
			t.Fatalf("unsupported profile was accepted for %q", args[0])
		}
		if stdout.Len() != 0 {
			t.Fatalf("rejected command wrote stdout for %q", args[0])
		}
	}
}
