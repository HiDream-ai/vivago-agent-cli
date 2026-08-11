package sse

import (
	"bufio"
	"encoding/json"
	"io"
	"strings"
)

type Event struct {
	EventID *string `json:"event_id"`
	Event   string  `json:"event"`
	Data    any     `json:"data"`
}

type Decoder struct {
	reader *bufio.Reader
}

func NewDecoder(reader io.Reader) *Decoder {
	return &Decoder{reader: bufio.NewReader(reader)}
}

func (decoder *Decoder) Decode() (Event, error) {
	var eventID *string
	eventName := ""
	dataParts := make([]string, 0)
	hasField := false

	for {
		line, err := decoder.reader.ReadString('\n')
		if err != nil && err != io.EOF {
			return Event{}, err
		}
		line = strings.ToValidUTF8(line, "\uFFFD")
		line = strings.TrimSuffix(line, "\n")
		line = strings.TrimSuffix(line, "\r")

		if line == "" {
			if hasField {
				return buildEvent(eventID, eventName, dataParts), nil
			}
		} else if !strings.HasPrefix(line, ":") {
			field, value, found := strings.Cut(line, ":")
			if !found {
				value = ""
			} else {
				value = strings.TrimPrefix(value, " ")
			}
			switch field {
			case "id":
				id := value
				eventID = &id
				hasField = true
			case "event":
				eventName = value
				hasField = true
			case "data":
				dataParts = append(dataParts, value)
				hasField = true
			}
		}

		if err == io.EOF {
			if hasField {
				return buildEvent(eventID, eventName, dataParts), nil
			}
			return Event{}, io.EOF
		}
	}
}

func buildEvent(eventID *string, eventName string, dataParts []string) Event {
	if eventName == "" {
		eventName = "message"
	}
	rawData := strings.Join(dataParts, "\n")
	var data any
	if err := json.Unmarshal([]byte(rawData), &data); err != nil {
		data = rawData
	}
	return Event{EventID: eventID, Event: eventName, Data: data}
}
