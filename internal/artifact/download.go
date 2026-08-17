package artifact

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	imageLimit = int64(100 * 1024 * 1024)
	audioLimit = int64(500 * 1024 * 1024)
	videoLimit = int64(5 * 1024 * 1024 * 1024)
)

type IPResolver interface {
	LookupIPAddr(context.Context, string) ([]net.IPAddr, error)
}

type DownloadResult struct {
	Path        string `json:"path"`
	Bytes       int64  `json:"bytes"`
	ContentType string `json:"content_type"`
}

type Downloader struct {
	httpClient *http.Client
	limits     map[string]int64
}

type environmentProxyTransport struct {
	proxy    func(*http.Request) (*url.URL, error)
	direct   *http.Transport
	proxied  *http.Transport
	resolver IPResolver
}

func (transport *environmentProxyTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	selected, err := transport.transportFor(request)
	if err != nil {
		return nil, err
	}
	return selected.RoundTrip(request)
}

func (transport *environmentProxyTransport) transportFor(request *http.Request) (http.RoundTripper, error) {
	proxyURL, err := transport.proxy(request)
	if err != nil {
		return nil, fmt.Errorf("select environment proxy")
	}
	if proxyURL == nil {
		return transport.direct, nil
	}
	if err := validateArtifactTarget(request.URL); err != nil {
		return nil, err
	}
	if _, err := resolvePublicAddresses(request.Context(), transport.resolver, request.URL.Hostname()); err != nil {
		return nil, err
	}
	return transport.proxied, nil
}

func NewDownloader(transport http.RoundTripper) *Downloader {
	var httpClient *http.Client
	if transport == nil {
		httpClient = newSecureHTTPClient(net.DefaultResolver)
	} else {
		httpClient = &http.Client{
			Transport:     transport,
			CheckRedirect: secureRedirectPolicy(),
		}
	}
	return &Downloader{
		httpClient: httpClient,
		limits: map[string]int64{
			"image": imageLimit,
			"audio": audioLimit,
			"video": videoLimit,
		},
	}
}

func (downloader *Downloader) Download(
	ctx context.Context,
	mediaType, contentID, outputPath string,
) (DownloadResult, error) {
	mediaType = strings.ToLower(strings.TrimSpace(mediaType))
	resolvedURL, err := ResolvePublicURL(mediaType, contentID, 0)
	if err != nil {
		return DownloadResult{}, err
	}
	limit, ok := downloader.limits[mediaType]
	if !ok || limit <= 0 {
		return DownloadResult{}, fmt.Errorf("download limit is unavailable")
	}
	destination, err := filepath.Abs(outputPath)
	if err != nil || strings.TrimSpace(outputPath) == "" {
		return DownloadResult{}, invalidArgument("output path is invalid")
	}
	if _, err := os.Lstat(destination); err == nil {
		return DownloadResult{}, invalidArgument("output path already exists")
	} else if !os.IsNotExist(err) {
		return DownloadResult{}, fmt.Errorf("inspect output path: %w", err)
	}
	parent := filepath.Dir(destination)
	parentInfo, err := os.Stat(parent)
	if err != nil || !parentInfo.IsDir() {
		return DownloadResult{}, invalidArgument("output directory is unavailable")
	}

	request, err := http.NewRequestWithContext(ctx, http.MethodGet, resolvedURL, nil)
	if err != nil {
		return DownloadResult{}, fmt.Errorf("create artifact request: %w", err)
	}
	response, err := downloader.httpClient.Do(request)
	if err != nil {
		return DownloadResult{}, fmt.Errorf("download artifact")
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return DownloadResult{}, fmt.Errorf("artifact download failed with HTTP %d", response.StatusCode)
	}
	contentType, _, err := mime.ParseMediaType(response.Header.Get("Content-Type"))
	if err != nil || !matchesMediaType(mediaType, contentType) {
		return DownloadResult{}, fmt.Errorf("artifact content type does not match media type")
	}
	if response.ContentLength > limit {
		return DownloadResult{}, fmt.Errorf("artifact exceeds download size limit")
	}

	temporary, err := os.CreateTemp(parent, ".vivago-agent-download-*")
	if err != nil {
		return DownloadResult{}, fmt.Errorf("create temporary artifact: %w", err)
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)
	bytesWritten, copyErr := io.Copy(temporary, io.LimitReader(response.Body, limit+1))
	if copyErr == nil && bytesWritten > limit {
		copyErr = fmt.Errorf("artifact exceeds download size limit")
	}
	if copyErr == nil {
		copyErr = temporary.Sync()
	}
	closeErr := temporary.Close()
	if copyErr != nil {
		return DownloadResult{}, copyErr
	}
	if closeErr != nil {
		return DownloadResult{}, fmt.Errorf("close temporary artifact: %w", closeErr)
	}
	if err := os.Link(temporaryPath, destination); err != nil {
		return DownloadResult{}, fmt.Errorf("publish artifact without overwrite: %w", err)
	}
	return DownloadResult{
		Path:        destination,
		Bytes:       bytesWritten,
		ContentType: contentType,
	}, nil
}

func (downloader *Downloader) Preview(
	ctx context.Context,
	mediaType, contentID string,
) (DownloadResult, error) {
	mediaType = strings.ToLower(strings.TrimSpace(mediaType))
	resolvedURL, err := ResolvePublicURL(mediaType, contentID, 0)
	if err != nil {
		return DownloadResult{}, err
	}
	parsed, err := url.Parse(resolvedURL)
	if err != nil {
		return DownloadResult{}, fmt.Errorf("parse artifact URL")
	}
	allowedExtensions := map[string]map[string]bool{
		"image": {".jpg": true, ".jpeg": true, ".png": true, ".webp": true},
		"video": {".mp4": true, ".mov": true, ".webm": true},
		"audio": {".mp3": true, ".m4a": true, ".wav": true, ".aac": true, ".ogg": true},
	}
	defaultExtensions := map[string]string{"image": ".jpg", "video": ".mp4", "audio": ".mp3"}
	extension := strings.ToLower(filepath.Ext(parsed.Path))
	if !allowedExtensions[mediaType][extension] {
		extension = defaultExtensions[mediaType]
	}
	previewDirectory, err := os.MkdirTemp("", "vivago-agent-preview-*")
	if err != nil {
		return DownloadResult{}, fmt.Errorf("create preview directory: %w", err)
	}
	result, err := downloader.Download(
		ctx,
		mediaType,
		resolvedURL,
		filepath.Join(previewDirectory, "preview"+extension),
	)
	if err != nil {
		_ = os.RemoveAll(previewDirectory)
		return DownloadResult{}, err
	}
	return result, nil
}

func matchesMediaType(mediaType, contentType string) bool {
	switch mediaType {
	case "image":
		return strings.HasPrefix(contentType, "image/")
	case "video":
		return strings.HasPrefix(contentType, "video/")
	case "audio":
		return strings.HasPrefix(contentType, "audio/")
	default:
		return false
	}
}

func newSecureHTTPClient(resolver IPResolver) *http.Client {
	dialer := &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}
	direct := newHTTPTransport(nil, dialer.DialContext)
	direct.DialContext = func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil || port != "443" ||
			(!strings.EqualFold(host, imageHost) && !strings.EqualFold(host, mediaHost)) {
			return nil, fmt.Errorf("artifact connection target is not allowed")
		}
		addresses, err := resolvePublicAddresses(ctx, resolver, host)
		if err != nil {
			return nil, err
		}
		var lastErr error
		for _, resolved := range addresses {
			connection, dialErr := dialer.DialContext(ctx, network, net.JoinHostPort(resolved.IP.String(), port))
			if dialErr == nil {
				return connection, nil
			}
			lastErr = dialErr
		}
		return nil, fmt.Errorf("connect to artifact host: %w", lastErr)
	}
	proxied := newHTTPTransport(http.ProxyFromEnvironment, dialer.DialContext)
	return &http.Client{
		Transport: &environmentProxyTransport{
			proxy:    http.ProxyFromEnvironment,
			direct:   direct,
			proxied:  proxied,
			resolver: resolver,
		},
		CheckRedirect: secureRedirectPolicy(),
	}
}

func newHTTPTransport(
	proxy func(*http.Request) (*url.URL, error),
	dialContext func(context.Context, string, string) (net.Conn, error),
) *http.Transport {
	return &http.Transport{
		Proxy:                 proxy,
		DialContext:           dialContext,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          4,
		IdleConnTimeout:       30 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ResponseHeaderTimeout: 30 * time.Second,
		ExpectContinueTimeout: time.Second,
		TLSClientConfig:       &tls.Config{MinVersion: tls.VersionTLS12},
	}
}

func validateArtifactTarget(parsed *url.URL) error {
	if parsed == nil || parsed.Scheme != "https" || parsed.Opaque != "" || parsed.Hostname() == "" {
		return fmt.Errorf("artifact target must use HTTPS")
	}
	if parsed.User != nil || parsed.Fragment != "" {
		return fmt.Errorf("artifact target contains forbidden authority or fragment data")
	}
	if port := parsed.Port(); port != "" && port != "443" {
		return fmt.Errorf("artifact target uses a forbidden port")
	}
	if !strings.EqualFold(parsed.Hostname(), imageHost) && !strings.EqualFold(parsed.Hostname(), mediaHost) {
		return fmt.Errorf("artifact target host is not allowed")
	}
	return nil
}

func resolvePublicAddresses(
	ctx context.Context,
	resolver IPResolver,
	host string,
) ([]net.IPAddr, error) {
	addresses, err := resolver.LookupIPAddr(ctx, host)
	if err != nil || len(addresses) == 0 {
		return nil, fmt.Errorf("resolve artifact host")
	}
	for _, address := range addresses {
		ip := address.IP
		if ip == nil || !ip.IsGlobalUnicast() || ip.IsPrivate() || ip.IsLoopback() ||
			ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsUnspecified() {
			return nil, fmt.Errorf("artifact host resolved to a non-public address")
		}
	}
	return addresses, nil
}

func secureRedirectPolicy() func(*http.Request, []*http.Request) error {
	return func(request *http.Request, previous []*http.Request) error {
		if len(previous) == 0 || len(previous) >= 10 {
			return fmt.Errorf("artifact redirect chain is invalid")
		}
		originalHost := previous[0].URL.Hostname()
		if request.URL.Scheme != "https" || request.URL.User != nil || request.URL.Fragment != "" ||
			!strings.EqualFold(request.URL.Hostname(), originalHost) {
			return fmt.Errorf("artifact redirect target is not allowed")
		}
		if port := request.URL.Port(); port != "" && port != "443" {
			return fmt.Errorf("artifact redirect port is not allowed")
		}
		return nil
	}
}
