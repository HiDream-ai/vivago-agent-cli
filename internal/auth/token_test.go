package auth

import (
	"encoding/base64"
	"fmt"
	"testing"
	"time"
)

func unsignedTestJWT(expiry time.Time) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"none"}`))
	payload := base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf(`{"exp":%d}`, expiry.Unix())))
	return header + "." + payload + ".signature"
}

func TestTicketNeedsRefreshSixtySecondsBeforeExpiry(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	tests := []struct {
		name   string
		ticket string
		want   bool
	}{
		{name: "more than sixty seconds", ticket: unsignedTestJWT(now.Add(61 * time.Second)), want: false},
		{name: "inside refresh window", ticket: unsignedTestJWT(now.Add(59 * time.Second)), want: true},
		{name: "malformed ticket", ticket: "not-a-jwt", want: true},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			if got := TicketNeedsRefresh(testCase.ticket, now); got != testCase.want {
				t.Fatalf("TicketNeedsRefresh() = %v, want %v", got, testCase.want)
			}
		})
	}
}
