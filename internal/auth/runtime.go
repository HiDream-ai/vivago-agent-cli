package auth

import (
	"context"
	"errors"
	"time"
)

type CommandRuntimeOptions struct {
	Now       func() time.Time
	LoginFlow LoginFlowOptions
	Refresher CredentialRefresher
}

type CredentialRefresher interface {
	Refresh(context.Context) error
}

type RefreshResult struct {
	Refreshed bool   `json:"refreshed"`
	Backend   string `json:"backend"`
}

type CommandRuntime struct {
	service   *Service
	login     *LoginFlow
	loginURL  string
	refresher CredentialRefresher
}

func NewCommandRuntime(
	store CredentialStore,
	loginURL string,
	openURL OpenURL,
	options CommandRuntimeOptions,
) *CommandRuntime {
	return &CommandRuntime{
		service:   NewService(store, options.Now),
		login:     NewLoginFlow(store, openURL, options.LoginFlow),
		loginURL:  loginURL,
		refresher: options.Refresher,
	}
}

func (runtime *CommandRuntime) Status(ctx context.Context) (Status, error) {
	return runtime.service.Status(ctx)
}

func (runtime *CommandRuntime) Login(ctx context.Context) (LoginResult, error) {
	return runtime.login.Login(ctx, runtime.loginURL)
}

func (runtime *CommandRuntime) Logout(ctx context.Context) error {
	return runtime.service.Logout(ctx)
}

func (runtime *CommandRuntime) Refresh(ctx context.Context) (RefreshResult, error) {
	if runtime.refresher == nil {
		return RefreshResult{}, errors.New("credential refresher is unavailable")
	}
	if err := runtime.refresher.Refresh(ctx); err != nil {
		return RefreshResult{}, err
	}
	return RefreshResult{Refreshed: true, Backend: runtime.service.store.Backend()}, nil
}
