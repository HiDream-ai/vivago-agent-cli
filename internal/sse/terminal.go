package sse

func TerminalType(event Event) string {
	candidate := event.Event
	if data, ok := event.Data.(map[string]any); ok {
		if dataType, ok := data["type"].(string); ok && dataType != "" {
			candidate = dataType
		}
	}
	if candidate == "RUN_FINISHED" || candidate == "RUN_ERROR" {
		return candidate
	}
	return ""
}
