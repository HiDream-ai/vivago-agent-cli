package auth

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"time"
)

const defaultLoginTimeout = 5 * time.Minute

type OpenURL func(context.Context, string) error

type LoginFlowOptions struct {
	Timeout     time.Duration
	OnManualURL func(string)
	Lock        ProcessLock
}

type LoginResult struct {
	Backend string `json:"backend"`
}

type LoginFlow struct {
	store       CredentialStore
	openURL     OpenURL
	timeout     time.Duration
	onManualURL func(string)
	lock        ProcessLock
}

func NewLoginFlow(store CredentialStore, openURL OpenURL, options LoginFlowOptions) *LoginFlow {
	timeout := options.Timeout
	if timeout <= 0 {
		timeout = defaultLoginTimeout
	}
	processLock := options.Lock
	if processLock == nil {
		processLock = noopProcessLock{}
	}
	return &LoginFlow{
		store:       store,
		openURL:     openURL,
		timeout:     timeout,
		onManualURL: options.OnManualURL,
		lock:        processLock,
	}
}

func (flow *LoginFlow) Login(ctx context.Context, rawLoginURL string) (LoginResult, error) {
	var result LoginResult
	err := flow.lock.WithLock(ctx, func() error {
		var loginErr error
		result, loginErr = flow.loginLocked(ctx, rawLoginURL)
		return loginErr
	})
	return result, err
}

func (flow *LoginFlow) loginLocked(ctx context.Context, rawLoginURL string) (LoginResult, error) {
	listener, err := (&net.ListenConfig{}).Listen(ctx, "tcp4", "127.0.0.1:0")
	if err != nil {
		return LoginResult{}, fmt.Errorf("start loopback login callback: %w", err)
	}
	defer listener.Close()

	tcpAddress, ok := listener.Addr().(*net.TCPAddr)
	if !ok {
		return LoginResult{}, fmt.Errorf("resolve loopback login callback address")
	}
	state, err := GenerateState()
	if err != nil {
		return LoginResult{}, err
	}
	loginURL, err := BuildLoginURL(rawLoginURL, tcpAddress.Port, state)
	if err != nil {
		return LoginResult{}, err
	}

	handler := NewCallbackHandler(state)
	server := &http.Server{
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
	}
	serveErrors := make(chan error, 1)
	go func() {
		serveErrors <- server.Serve(listener)
	}()
	defer server.Close()

	if flow.openURL == nil || flow.openURL(ctx, loginURL) != nil {
		if flow.onManualURL != nil {
			flow.onManualURL(loginURL)
		}
	}

	timer := time.NewTimer(flow.timeout)
	defer timer.Stop()
	select {
	case credentials := <-handler.Result():
		if err := flow.store.Save(ctx, Credentials{
			Ticket:       credentials.Ticket,
			RefreshToken: credentials.RefreshToken,
		}); err != nil {
			return LoginResult{}, fmt.Errorf("save login credentials: %w", err)
		}
		return LoginResult{Backend: flow.store.Backend()}, nil
	case <-ctx.Done():
		return LoginResult{}, ctx.Err()
	case <-timer.C:
		return LoginResult{}, fmt.Errorf("login timed out")
	case serveErr := <-serveErrors:
		if errors.Is(serveErr, http.ErrServerClosed) {
			return LoginResult{}, fmt.Errorf("login callback stopped before completion")
		}
		return LoginResult{}, fmt.Errorf("serve loopback login callback: %w", serveErr)
	}
}
