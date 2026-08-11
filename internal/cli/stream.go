package cli

import (
	"encoding/json"
	"errors"
	"io"

	"github.com/HiDream-ai/vivago-agent-cli/internal/sse"
)

const (
	ExitBusiness = 30
	ExitNetwork  = 50
)

type Session struct {
	ConversationID string
	TurnID         string
}

type EventDecoder interface {
	Decode() (sse.Event, error)
}

func EmitStream(stdout io.Writer, session Session, decoder EventDecoder) int {
	encoder := json.NewEncoder(stdout)
	_ = encoder.Encode(map[string]any{
		"type":            "session",
		"conversation_id": session.ConversationID,
		"turn_id":         session.TurnID,
	})
	terminalType := ""
	var lastEventID *string
	for {
		event, err := decoder.Decode()
		if err != nil {
			if terminalType == "RUN_FINISHED" {
				return 0
			}
			if terminalType == "RUN_ERROR" {
				return ExitBusiness
			}
			errorCode := "STREAM_INTERRUPTED"
			errorMessage := "SSE stream was interrupted; resume the turn with last_event_id"
			if errors.Is(err, io.EOF) {
				errorCode = "STREAM_ENDED_EARLY"
				errorMessage = "SSE stream ended before RUN_FINISHED or RUN_ERROR; resume the turn with last_event_id"
			}
			_ = encoder.Encode(map[string]any{
				"type":            "stream_error",
				"conversation_id": session.ConversationID,
				"turn_id":         session.TurnID,
				"last_event_id":   lastEventID,
				"error": map[string]string{
					"code":    errorCode,
					"message": errorMessage,
				},
			})
			return ExitNetwork
		}
		_ = encoder.Encode(struct {
			Type string `json:"type"`
			sse.Event
		}{Type: "event", Event: event})
		if event.EventID != nil && *event.EventID != "" {
			id := *event.EventID
			lastEventID = &id
		}
		if candidate := sse.TerminalType(event); candidate != "" {
			terminalType = candidate
		}
	}
}
