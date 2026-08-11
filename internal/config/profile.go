package config

type Profile struct {
	Name                   string
	APIBaseURL             string
	WebBaseURL             string
	LoginURL               string
	AllowManualAuthRefresh bool
}

func Current() Profile {
	return currentProfile
}
