package upload

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/HiDream-ai/vivago-agent-cli/internal/attachment"
)

type IPResolver interface {
	LookupIPAddr(context.Context, string) ([]net.IPAddr, error)
}

type Uploader struct {
	httpClient *http.Client
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
	if err := validateUploadURL(request.URL.String()); err != nil {
		return nil, err
	}
	if err := validatePublicUploadHost(request.Context(), transport.resolver, request.URL.Hostname()); err != nil {
		return nil, err
	}
	return transport.proxied, nil
}

func New(transport http.RoundTripper) *Uploader {
	if transport != nil {
		return &Uploader{httpClient: &http.Client{
			Transport: transport,
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return fmt.Errorf("upload redirects are not allowed")
			},
		}}
	}
	return &Uploader{httpClient: newSecureHTTPClient(net.DefaultResolver)}
}

func (uploader *Uploader) Put(
	ctx context.Context,
	rawURL, _ string,
	item attachment.Attachment,
) error {
	if err := validateUploadURL(rawURL); err != nil {
		return err
	}
	info, err := os.Lstat(item.Path)
	if err != nil || !info.Mode().IsRegular() || info.Size() != item.Size {
		return fmt.Errorf("%w: attachment changed before upload", attachment.ErrInvalidArgument)
	}
	file, err := os.Open(item.Path)
	if err != nil {
		return fmt.Errorf("%w: attachment is not readable", attachment.ErrInvalidArgument)
	}
	defer file.Close()
	openedInfo, err := file.Stat()
	if err != nil || !openedInfo.Mode().IsRegular() || openedInfo.Size() != item.Size {
		return fmt.Errorf("%w: attachment changed before upload", attachment.ErrInvalidArgument)
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPut, rawURL, file)
	if err != nil {
		return fmt.Errorf("create upload request")
	}
	request.ContentLength = item.Size
	request.Header.Set("Content-Type", item.ContentType)
	response, err := uploader.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("upload attachment")
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 4096))
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("attachment upload failed with HTTP %d", response.StatusCode)
	}
	return nil
}

func validateUploadURL(rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil || parsed.Scheme != "https" || parsed.Opaque != "" || parsed.Hostname() == "" {
		return fmt.Errorf("upload URL must use HTTPS")
	}
	if parsed.User != nil || parsed.Fragment != "" {
		return fmt.Errorf("upload URL contains forbidden authority or fragment data")
	}
	if port := parsed.Port(); port != "" && port != "443" {
		return fmt.Errorf("upload URL uses a forbidden port")
	}
	if literalIP := net.ParseIP(parsed.Hostname()); literalIP != nil && !isPublicIP(literalIP) {
		return fmt.Errorf("upload URL uses a non-public address")
	}
	return nil
}

func newSecureHTTPClient(resolver IPResolver) *http.Client {
	dialer := &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}
	direct := newHTTPTransport(nil, dialer.DialContext)
	direct.DialContext = func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil || port != "443" {
			return nil, fmt.Errorf("upload connection target is not allowed")
		}
		addresses, err := resolvePublicUploadAddresses(ctx, resolver, host)
		if err != nil {
			return nil, err
		}
		var lastErr error
		for _, address := range addresses {
			connection, dialErr := dialer.DialContext(
				ctx,
				network,
				net.JoinHostPort(address.IP.String(), port),
			)
			if dialErr == nil {
				return connection, nil
			}
			lastErr = dialErr
		}
		return nil, fmt.Errorf("connect to upload host: %w", lastErr)
	}
	proxied := newHTTPTransport(http.ProxyFromEnvironment, dialer.DialContext)
	return &http.Client{
		Transport: &environmentProxyTransport{
			proxy:    http.ProxyFromEnvironment,
			direct:   direct,
			proxied:  proxied,
			resolver: resolver,
		},
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return fmt.Errorf("upload redirects are not allowed")
		},
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

func validatePublicUploadHost(ctx context.Context, resolver IPResolver, host string) error {
	_, err := resolvePublicUploadAddresses(ctx, resolver, host)
	return err
}

func resolvePublicUploadAddresses(
	ctx context.Context,
	resolver IPResolver,
	host string,
) ([]net.IPAddr, error) {
	addresses, err := resolver.LookupIPAddr(ctx, host)
	if err != nil || len(addresses) == 0 {
		return nil, fmt.Errorf("resolve upload host")
	}
	for _, address := range addresses {
		if !isPublicIP(address.IP) {
			return nil, fmt.Errorf("upload host resolved to a non-public address")
		}
	}
	return addresses, nil
}

func isPublicIP(ip net.IP) bool {
	return ip != nil && ip.IsGlobalUnicast() && !ip.IsPrivate() && !ip.IsLoopback() &&
		!ip.IsLinkLocalUnicast() && !ip.IsLinkLocalMulticast() && !ip.IsUnspecified() &&
		!strings.HasPrefix(ip.String(), "0.")
}
