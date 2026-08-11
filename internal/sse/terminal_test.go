package sse

import "testing"

func TestTerminalTypePrefersDataTypeAndFallsBackToEventName(t *testing.T) {
	cases := []struct {
		name  string
		event Event
		want  string
	}{
		{
			name:  "finished in data",
			event: Event{Event: "message", Data: map[string]any{"type": "RUN_FINISHED"}},
			want:  "RUN_FINISHED",
		},
		{
			name:  "error in event name",
			event: Event{Event: "RUN_ERROR", Data: map[string]any{}},
			want:  "RUN_ERROR",
		},
		{
			name:  "non-terminal event",
			event: Event{Event: "message", Data: map[string]any{"type": "TEXT_MESSAGE_CONTENT"}},
			want:  "",
		},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			if got := TerminalType(testCase.event); got != testCase.want {
				t.Fatalf("terminal type = %q, want %q", got, testCase.want)
			}
		})
	}
}
