//go:build prod

package config

var currentProfile = Profile{
	Name:                   "prod",
	APIBaseURL:             "https://vivago.ai",
	WebBaseURL:             "https://vivago.ai",
	LoginURL:               "https://vivago.ai/agent/login",
	AllowManualAuthRefresh: false,
}
