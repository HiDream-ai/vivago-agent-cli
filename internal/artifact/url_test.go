package artifact

import "testing"

func TestResolvePublicURLUsesOverseasHosts(t *testing.T) {
	tests := []struct {
		mediaType string
		contentID string
		width     int
		want      string
	}{
		{
			mediaType: "image",
			contentID: "p_image",
			want:      "https://storage.vivago.ai/image/p_image.jpg",
		},
		{
			mediaType: "image",
			contentID: "folder/cat image",
			width:     512,
			want:      "https://storage.vivago.ai/image/folder/cat%20image.jpg?width=512",
		},
		{
			mediaType: "video",
			contentID: "v_video",
			want:      "https://media.vivago.ai/v_video.mp4",
		},
		{
			mediaType: "video",
			contentID: "v_video.mp4",
			want:      "https://media.vivago.ai/v_video.mp4",
		},
		{
			mediaType: "audio",
			contentID: "audio/a_track.mp3",
			want:      "https://media.vivago.ai/audio/a_track.mp3",
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.mediaType+"/"+testCase.contentID, func(t *testing.T) {
			got, err := ResolvePublicURL(testCase.mediaType, testCase.contentID, testCase.width)
			if err != nil {
				t.Fatalf("resolve: %v", err)
			}
			if got != testCase.want {
				t.Fatalf("URL = %q, want %q", got, testCase.want)
			}
		})
	}
}

func TestResolvePublicURLAcceptsOnlyMatchingTrustedHTTPSURL(t *testing.T) {
	tests := []struct {
		mediaType string
		rawURL    string
		wantOK    bool
	}{
		{"image", "https://storage.vivago.ai/image/p.png?width=512", true},
		{"video", "https://media.vivago.ai/v.mp4", true},
		{"audio", "https://media.vivago.ai/a.mp3", true},
		{"image", "http://storage.vivago.ai/image/p.png", false},
		{"image", "https://media.vivago.ai/image/p.png", false},
		{"video", "https://storage.vivago.ai/v.mp4", false},
		{"image", "https://storage.vivago.ai.evil.test/p.png", false},
		{"image", "https://user:pass@storage.vivago.ai/p.png", false},
		{"image", "https://storage.vivago.ai:444/p.png", false},
		{"image", "https://127.0.0.1/p.png", false},
	}
	for _, testCase := range tests {
		t.Run(testCase.rawURL, func(t *testing.T) {
			got, err := ResolvePublicURL(testCase.mediaType, testCase.rawURL, 0)
			if testCase.wantOK {
				if err != nil || got != testCase.rawURL {
					t.Fatalf("got %q, err %v", got, err)
				}
				return
			}
			if err == nil {
				t.Fatalf("unsafe URL accepted as %q", got)
			}
		})
	}
}

func TestResolvePublicURLRejectsUnsafeContentIDsAndArguments(t *testing.T) {
	tests := []struct {
		mediaType string
		contentID string
		width     int
	}{
		{"", "p", 0},
		{"document", "p", 0},
		{"image", "", 0},
		{"image", "../secret", 0},
		{"image", "/absolute", 0},
		{"image", "p?redirect=https://evil.test", 0},
		{"image", "p", -1},
		{"video", "v", 512},
	}
	for _, testCase := range tests {
		if got, err := ResolvePublicURL(testCase.mediaType, testCase.contentID, testCase.width); err == nil {
			t.Fatalf("ResolvePublicURL(%q, %q, %d) = %q", testCase.mediaType, testCase.contentID, testCase.width, got)
		}
	}
}
