package sse

import (
	"io"
	"strings"
	"testing"
)

func TestDecoderParsesIDEventAndJSONData(t *testing.T) {
	decoder := NewDecoder(strings.NewReader(
		"id: 12-0\n" +
			"event: RUN_STARTED\n" +
			"data: {\"runId\":\"r-1\"}\n\n",
	))

	event, err := decoder.Decode()
	if err != nil {
		t.Fatalf("decode event: %v", err)
	}
	if event.EventID == nil || *event.EventID != "12-0" {
		t.Fatalf("event ID = %#v", event.EventID)
	}
	if event.Event != "RUN_STARTED" {
		t.Fatalf("event = %q", event.Event)
	}
	data, ok := event.Data.(map[string]any)
	if !ok || data["runId"] != "r-1" {
		t.Fatalf("data = %#v", event.Data)
	}
	if _, err := decoder.Decode(); err != io.EOF {
		t.Fatalf("second decode error = %v, want EOF", err)
	}
}

func TestDecoderPreservesNonJSONMultilineDataAndIgnoresHeartbeat(t *testing.T) {
	decoder := NewDecoder(strings.NewReader(
		": heartbeat\n" +
			"data: first\n" +
			"data: second\n\n",
	))

	event, err := decoder.Decode()
	if err != nil {
		t.Fatalf("decode event: %v", err)
	}
	if event.Event != "message" {
		t.Fatalf("event = %q, want message", event.Event)
	}
	if event.Data != "first\nsecond" {
		t.Fatalf("data = %#v", event.Data)
	}
}
