package config

type Profile struct {
	Name       string
	APIBaseURL string
	WebBaseURL string
	LoginURL   string
}

func Current() Profile {
	return currentProfile
}
