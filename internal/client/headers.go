package client

import (
	"fmt"
	"net/http"
)

type Metadata struct {
	Version string
	OS      string
	Arch    string
	Host    string
}

func RequestHeaders(accessToken string, metadata Metadata) http.Header {
	headers := make(http.Header)
	headers.Set("Authorization", "Bearer "+accessToken)
	headers.Set("Content-Type", "application/json")
	headers.Set("X-Source", "cli")
	headers.Set("X-Client-Platform", "web")
	headers.Set("X-Client-Version", metadata.Version)
	headers.Set(
		"User-Agent",
		fmt.Sprintf(
			"vivago-agent-cli/%s (%s; %s; %s)",
			metadata.Version,
			metadata.OS,
			metadata.Arch,
			metadata.Host,
		),
	)
	return headers
}
