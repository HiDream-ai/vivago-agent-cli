//go:build !prod

package config

var currentProfile = Profile{
	Name:                   "dev",
	APIBaseURL:             "https://dev.vivago.ai",
	WebBaseURL:             "https://dev.vivago.ai",
	LoginURL:               "https://dev.vivago.ai/agent/login",
	AllowManualAuthRefresh: true,
}
