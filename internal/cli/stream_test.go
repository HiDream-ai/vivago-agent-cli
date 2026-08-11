package cli

import (
	"bytes"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/HiDream-ai/vivago-agent-cli/internal/sse"
)

func TestEmitStreamWritesSessionBeforeEventsAndFinishesSuccessfully(t *testing.T) {
	decoder := sse.NewDecoder(strings.NewReader(
		"id: 1-0\n" +
			"event: message\n" +
			"data: {\"type\":\"RUN_STARTED\"}\n\n" +
			"id: 2-0\n" +
			"event: message\n" +
			"data: {\"type\":\"RUN_FINISHED\"}\n\n",
	))
	var stdout bytes.Buffer

	exitCode := EmitStream(&stdout, Session{
		ConversationID: "c-1",
		TurnID:         "t-1",
	}, decoder)

	if exitCode != 0 {
		t.Fatalf("exit code = %d, want 0", exitCode)
	}
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	if len(lines) != 3 {
		t.Fatalf("line count = %d\n%s", len(lines), stdout.String())
	}
	var session map[string]any
	if err := json.Unmarshal([]byte(lines[0]), &session); err != nil {
		t.Fatalf("decode session line: %v", err)
	}
	if session["type"] != "session" || session["conversation_id"] != "c-1" || session["turn_id"] != "t-1" {
		t.Fatalf("session = %#v", session)
	}
	var finished map[string]any
	if err := json.Unmarshal([]byte(lines[2]), &finished); err != nil {
		t.Fatalf("decode finished line: %v", err)
	}
	if finished["type"] != "event" || finished["event_id"] != "2-0" {
		t.Fatalf("finished event = %#v", finished)
	}
}

func TestEmitStreamExposesResumeCursorWhenStreamEndsEarly(t *testing.T) {
	decoder := sse.NewDecoder(strings.NewReader(
		"id: 9-0\n" +
			"event: message\n" +
			"data: {\"type\":\"TEXT_MESSAGE_CONTENT\",\"delta\":\"partial\"}\n\n",
	))
	var stdout bytes.Buffer

	exitCode := EmitStream(&stdout, Session{
		ConversationID: "c-incomplete",
		TurnID:         "t-incomplete",
	}, decoder)

	if exitCode != ExitNetwork {
		t.Fatalf("exit code = %d, want %d", exitCode, ExitNetwork)
	}
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	if len(lines) != 3 {
		t.Fatalf("line count = %d, want 3\n%s", len(lines), stdout.String())
	}
	var streamError struct {
		Type           string `json:"type"`
		ConversationID string `json:"conversation_id"`
		TurnID         string `json:"turn_id"`
		LastEventID    string `json:"last_event_id"`
		Error          struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if err := json.Unmarshal([]byte(lines[2]), &streamError); err != nil {
		t.Fatalf("decode stream error: %v", err)
	}
	if streamError.Type != "stream_error" || streamError.ConversationID != "c-incomplete" ||
		streamError.TurnID != "t-incomplete" || streamError.LastEventID != "9-0" ||
		streamError.Error.Code != "STREAM_ENDED_EARLY" {
		t.Fatalf("stream error = %#v", streamError)
	}
}

func TestEmitStreamRedactsDecoderErrors(t *testing.T) {
	var stdout bytes.Buffer
	exitCode := EmitStream(&stdout, Session{
		ConversationID: "c-1",
		TurnID:         "t-1",
	}, failingEventDecoder{err: errors.New("read failed with Bearer secret-ticket")})

	if exitCode != ExitNetwork {
		t.Fatalf("exit code = %d", exitCode)
	}
	if strings.Contains(stdout.String(), "secret-ticket") || strings.Contains(stdout.String(), "Bearer") {
		t.Fatalf("stream output leaked decoder error: %s", stdout.String())
	}
	if !strings.Contains(stdout.String(), `"code":"STREAM_INTERRUPTED"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

type failingEventDecoder struct {
	err error
}

func (decoder failingEventDecoder) Decode() (sse.Event, error) {
	return sse.Event{}, decoder.err
}
