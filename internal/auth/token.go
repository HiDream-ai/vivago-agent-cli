package auth

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"time"
)

const ticketRefreshWindow = 60 * time.Second

func TicketNeedsRefresh(ticket string, now time.Time) bool {
	parts := strings.Split(ticket, ".")
	if len(parts) != 3 {
		return true
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return true
	}
	var claims struct {
		ExpiresAt int64 `json:"exp"`
	}
	if err := json.Unmarshal(payload, &claims); err != nil || claims.ExpiresAt <= 0 {
		return true
	}
	expiresAt := time.Unix(claims.ExpiresAt, 0)
	return !expiresAt.After(now.Add(ticketRefreshWindow))
}
