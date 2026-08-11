package attachment

import (
	"os"
	"path/filepath"
	"testing"
)

func TestValidateRecognizesSupportedFormats(t *testing.T) {
	directory := t.TempDir()
	tests := []struct {
		name        string
		mediaType   string
		bucket      string
		contentType string
	}{
		{"cat.jpg", "image", "hidreamai-image", "image/jpeg"},
		{"cat.png", "image", "hidreamai-image", "image/png"},
		{"clip.mp4", "video", "hidreamai-media", "video/mp4"},
		{"voice.mp3", "audio", "hidreamai-media", "audio/mpeg"},
		{"brief.pdf", "document", "hidreamai-media", "application/pdf"},
		{"captions.srt", "document", "hidreamai-media", "application/x-subrip"},
		{"captions.vtt", "document", "hidreamai-media", "text/vtt"},
		{"captions.ass", "document", "hidreamai-media", "text/x-ssa"},
	}
	for _, testCase := range tests {
		path := filepath.Join(directory, testCase.name)
		if err := os.WriteFile(path, []byte("content"), 0o600); err != nil {
			t.Fatal(err)
		}
		attachments, err := Validate([]string{path})
		if err != nil {
			t.Fatalf("validate %s: %v", testCase.name, err)
		}
		got := attachments[0]
		if got.Path != path || got.Name != testCase.name || got.MediaType != testCase.mediaType ||
			got.Bucket != testCase.bucket || got.ContentType != testCase.contentType {
			t.Fatalf("attachment = %#v", got)
		}
	}
}

func TestValidateRejectsSymlinkDirectoryDeviceAndUnsupportedFormat(t *testing.T) {
	directory := t.TempDir()
	regular := filepath.Join(directory, "cat.png")
	if err := os.WriteFile(regular, []byte("png"), 0o600); err != nil {
		t.Fatal(err)
	}
	symlink := filepath.Join(directory, "linked.png")
	if err := os.Symlink(regular, symlink); err != nil {
		t.Fatal(err)
	}
	unsupported := filepath.Join(directory, "archive.zip")
	if err := os.WriteFile(unsupported, []byte("zip"), 0o600); err != nil {
		t.Fatal(err)
	}
	for _, path := range []string{symlink, directory, "/dev/null", unsupported} {
		if _, err := Validate([]string{path}); err == nil {
			t.Fatalf("unsafe attachment accepted: %s", path)
		}
	}
}

func TestValidateEnforcesCountsDistinctDocumentsAndSizes(t *testing.T) {
	directory := t.TempDir()
	images := make([]string, 0, 10)
	for index := 0; index < 10; index++ {
		path := filepath.Join(directory, "image-"+string(rune('a'+index))+".png")
		if err := os.WriteFile(path, []byte("png"), 0o600); err != nil {
			t.Fatal(err)
		}
		images = append(images, path)
	}
	if _, err := Validate(images); err == nil {
		t.Fatal("ten image attachments were accepted")
	}

	documents := []string{filepath.Join(directory, "one.pdf"), filepath.Join(directory, "two.pdf")}
	for _, path := range documents {
		if err := os.WriteFile(path, []byte("pdf"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := Validate(documents); err == nil {
		t.Fatal("duplicate document suffixes were accepted")
	}

	largeImage := filepath.Join(directory, "large.png")
	file, err := os.Create(largeImage)
	if err != nil {
		t.Fatal(err)
	}
	if err := file.Truncate(50*1024*1024 + 1); err != nil {
		t.Fatal(err)
	}
	_ = file.Close()
	if _, err := Validate([]string{largeImage}); err == nil {
		t.Fatal("oversized image was accepted")
	}
}
