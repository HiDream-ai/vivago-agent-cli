package auth

import (
	"context"
	"reflect"
	"testing"
)

func TestBrowserOpenerUsesPlatformCommandWithoutShell(t *testing.T) {
	tests := []struct {
		platform string
		name     string
		args     []string
	}{
		{platform: "darwin", name: "open", args: []string{"https://vivago.ai/agent/login?state=test"}},
		{platform: "linux", name: "xdg-open", args: []string{"https://vivago.ai/agent/login?state=test"}},
		{
			platform: "windows",
			name:     "rundll32",
			args:     []string{"url.dll,FileProtocolHandler", "https://vivago.ai/agent/login?state=test"},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.platform, func(t *testing.T) {
			runner := &recordingCommandRunner{}
			opener := NewBrowserOpener(testCase.platform, runner)
			if err := opener(context.Background(), "https://vivago.ai/agent/login?state=test"); err != nil {
				t.Fatalf("open browser: %v", err)
			}
			if runner.name != testCase.name || !reflect.DeepEqual(runner.args, testCase.args) {
				t.Fatalf("command = %q %#v", runner.name, runner.args)
			}
		})
	}
}

type recordingCommandRunner struct {
	name string
	args []string
}

func (runner *recordingCommandRunner) Run(_ context.Context, name string, args ...string) error {
	runner.name = name
	runner.args = append([]string(nil), args...)
	return nil
}
