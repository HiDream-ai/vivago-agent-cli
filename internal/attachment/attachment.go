package attachment

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

var ErrInvalidArgument = errors.New("invalid attachment")

type Attachment struct {
	Path        string
	Name        string
	Suffix      string
	MediaType   string
	Bucket      string
	ContentType string
	Size        int64
}

type format struct {
	mediaType   string
	bucket      string
	contentType string
}

var formats = map[string]format{
	".jpg":  {"image", "hidreamai-image", "image/jpeg"},
	".jpeg": {"image", "hidreamai-image", "image/jpeg"},
	".png":  {"image", "hidreamai-image", "image/png"},
	".mp4":  {"video", "hidreamai-media", "video/mp4"},
	".mp3":  {"audio", "hidreamai-media", "audio/mpeg"},
	".doc":  {"document", "hidreamai-media", "application/msword"},
	".docx": {
		"document",
		"hidreamai-media",
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	},
	".txt": {"document", "hidreamai-media", "text/plain"},
	".md":  {"document", "hidreamai-media", "text/markdown"},
	".pdf": {"document", "hidreamai-media", "application/pdf"},
	".srt": {"document", "hidreamai-media", "application/x-subrip"},
	".vtt": {"document", "hidreamai-media", "text/vtt"},
	".ass": {"document", "hidreamai-media", "text/x-ssa"},
	".ssa": {"document", "hidreamai-media", "text/x-ssa"},
}

var countLimits = map[string]int{"image": 9, "video": 1, "audio": 1, "document": 4}

var sizeLimits = map[string]int64{
	"image":    50 * 1024 * 1024,
	"video":    300 * 1024 * 1024,
	"audio":    15 * 1024 * 1024,
	"document": 1024 * 1024,
}

func Validate(paths []string) ([]Attachment, error) {
	attachments := make([]Attachment, 0, len(paths))
	counts := map[string]int{}
	documentSuffixes := map[string]bool{}
	for _, rawPath := range paths {
		if strings.TrimSpace(rawPath) == "" {
			return nil, invalid("attachment path is required")
		}
		absolutePath, err := filepath.Abs(rawPath)
		if err != nil {
			return nil, invalid("attachment path is invalid")
		}
		info, err := os.Lstat(absolutePath)
		if err != nil || !info.Mode().IsRegular() {
			return nil, invalid("attachment must be a regular file")
		}
		file, err := os.Open(absolutePath)
		if err != nil {
			return nil, invalid("attachment is not readable")
		}
		_ = file.Close()

		suffix := strings.ToLower(filepath.Ext(absolutePath))
		attachmentFormat, ok := formats[suffix]
		if !ok {
			return nil, invalid("attachment format is not supported")
		}
		counts[attachmentFormat.mediaType]++
		if counts[attachmentFormat.mediaType] > countLimits[attachmentFormat.mediaType] {
			return nil, invalid("too many attachments for media type")
		}
		if info.Size() > sizeLimits[attachmentFormat.mediaType] {
			return nil, invalid("attachment exceeds size limit")
		}
		if attachmentFormat.mediaType == "document" {
			if documentSuffixes[suffix] {
				return nil, invalid("only one document of each format is allowed")
			}
			documentSuffixes[suffix] = true
		}
		attachments = append(attachments, Attachment{
			Path:        absolutePath,
			Name:        filepath.Base(absolutePath),
			Suffix:      suffix,
			MediaType:   attachmentFormat.mediaType,
			Bucket:      attachmentFormat.bucket,
			ContentType: attachmentFormat.contentType,
			Size:        info.Size(),
		})
	}
	return attachments, nil
}

func invalid(message string) error {
	return fmt.Errorf("%w: %s", ErrInvalidArgument, message)
}
