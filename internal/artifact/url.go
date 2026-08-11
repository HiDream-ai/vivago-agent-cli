package artifact

import (
	"errors"
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"unicode"
)

const (
	imageHost = "storage.vivago.ai"
	mediaHost = "media.vivago.ai"
)

var ErrInvalidArgument = errors.New("invalid artifact argument")

func ResolvePublicURL(mediaType, contentID string, width int) (string, error) {
	mediaType = strings.ToLower(strings.TrimSpace(mediaType))
	contentID = strings.TrimSpace(contentID)
	if mediaType != "image" && mediaType != "video" && mediaType != "audio" {
		return "", invalidArgument("media type must be image, video, or audio")
	}
	if contentID == "" {
		return "", invalidArgument("content ID is required")
	}
	if width < 0 || (mediaType != "image" && width != 0) {
		return "", invalidArgument("width is valid only for images and must be greater than zero")
	}
	if strings.Contains(contentID, "://") {
		if width != 0 {
			return "", invalidArgument("width cannot modify an existing artifact URL")
		}
		if err := validateTrustedURL(mediaType, contentID); err != nil {
			return "", err
		}
		return contentID, nil
	}

	escapedID, err := escapeContentID(contentID)
	if err != nil {
		return "", err
	}
	var resolved string
	switch mediaType {
	case "image":
		resolved = "https://" + imageHost + "/image/" + escapedID + ".jpg"
		if width > 0 {
			resolved += "?width=" + strconv.Itoa(width)
		}
	case "video":
		if !strings.HasSuffix(strings.ToLower(escapedID), ".mp4") {
			escapedID += ".mp4"
		}
		resolved = "https://" + mediaHost + "/" + escapedID
	case "audio":
		resolved = "https://" + mediaHost + "/" + escapedID
	}
	return resolved, nil
}

func validateTrustedURL(mediaType, rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil || parsed.Scheme != "https" || parsed.Opaque != "" {
		return invalidArgument("artifact URL must use HTTPS")
	}
	if parsed.User != nil || parsed.Fragment != "" {
		return invalidArgument("artifact URL contains forbidden authority or fragment data")
	}
	if port := parsed.Port(); port != "" && port != "443" {
		return invalidArgument("artifact URL uses a forbidden port")
	}
	wantHost := mediaHost
	if mediaType == "image" {
		wantHost = imageHost
	}
	if !strings.EqualFold(parsed.Hostname(), wantHost) {
		return invalidArgument("artifact URL host is not allowed for media type")
	}
	return nil
}

func escapeContentID(contentID string) (string, error) {
	if strings.HasPrefix(contentID, "/") || strings.ContainsAny(contentID, "\\?#") {
		return "", invalidArgument("content ID contains forbidden path data")
	}
	segments := strings.Split(contentID, "/")
	escaped := make([]string, 0, len(segments))
	for _, segment := range segments {
		if segment == "" || segment == "." || segment == ".." ||
			strings.IndexFunc(segment, unicode.IsControl) >= 0 {
			return "", invalidArgument("content ID contains an unsafe path segment")
		}
		escaped = append(escaped, url.PathEscape(segment))
	}
	return strings.Join(escaped, "/"), nil
}

func invalidArgument(message string) error {
	return fmt.Errorf("%w: %s", ErrInvalidArgument, message)
}
