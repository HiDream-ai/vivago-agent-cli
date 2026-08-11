package auth

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"net/url"
	"regexp"
	"strconv"
)

var statePattern = regexp.MustCompile(`^[A-Za-z0-9_-]{32,128}$`)

func GenerateState() (string, error) {
	random := make([]byte, 32)
	if _, err := rand.Read(random); err != nil {
		return "", fmt.Errorf("generate login state: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(random), nil
}

func BuildLoginURL(rawLoginURL string, callbackPort int, state string) (string, error) {
	loginURL, err := url.Parse(rawLoginURL)
	if err != nil {
		return "", fmt.Errorf("parse login URL: %w", err)
	}
	if loginURL.Scheme != "https" || loginURL.Host == "" {
		return "", fmt.Errorf("login URL must use HTTPS")
	}
	if callbackPort < 1 || callbackPort > 65535 {
		return "", fmt.Errorf("callback port is out of range")
	}
	if !statePattern.MatchString(state) {
		return "", fmt.Errorf("state must be 32 to 128 URL-safe characters")
	}

	query := make(url.Values)
	query.Set("client", "vivago-agent-cli")
	query.Set("callback_port", strconv.Itoa(callbackPort))
	query.Set("state", state)
	loginURL.RawQuery = query.Encode()
	loginURL.Fragment = ""
	return loginURL.String(), nil
}
