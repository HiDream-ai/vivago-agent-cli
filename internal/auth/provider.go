package auth

import (
	"context"
	"errors"
	"fmt"
	"time"
)

var ErrLoginRequired = errors.New("login required")

type TokenRefresher interface {
	Refresh(context.Context, string) (string, error)
}

type ProviderOptions struct {
	Now        func() time.Time
	RetryDelay time.Duration
	Lock       ProcessLock
}

type StoredAuthProvider struct {
	store      CredentialStore
	refresher  TokenRefresher
	now        func() time.Time
	retryDelay time.Duration
	lock       ProcessLock
}

func NewStoredAuthProvider(
	store CredentialStore,
	refresher TokenRefresher,
	options ProviderOptions,
) *StoredAuthProvider {
	now := options.Now
	if now == nil {
		now = time.Now
	}
	retryDelay := options.RetryDelay
	if retryDelay < 0 {
		retryDelay = 0
	}
	processLock := options.Lock
	if processLock == nil {
		processLock = noopProcessLock{}
	}
	return &StoredAuthProvider{
		store:      store,
		refresher:  refresher,
		now:        now,
		retryDelay: retryDelay,
		lock:       processLock,
	}
}

func (provider *StoredAuthProvider) AccessToken(ctx context.Context) (string, error) {
	credentials, err := provider.store.Load(ctx)
	if errors.Is(err, ErrCredentialsNotFound) {
		return "", ErrLoginRequired
	}
	if err != nil {
		return "", fmt.Errorf("load authentication: %w", err)
	}
	if !TicketNeedsRefresh(credentials.Ticket, provider.now()) {
		return credentials.Ticket, nil
	}
	var ticket string
	err = provider.lock.WithLock(ctx, func() error {
		var refreshErr error
		ticket, refreshErr = provider.refreshLocked(ctx, false)
		return refreshErr
	})
	if err != nil {
		return "", err
	}
	return ticket, nil
}

func (provider *StoredAuthProvider) Refresh(ctx context.Context) error {
	return provider.lock.WithLock(ctx, func() error {
		_, err := provider.refreshLocked(ctx, true)
		return err
	})
}

func (provider *StoredAuthProvider) refreshLocked(ctx context.Context, force bool) (string, error) {
	credentials, err := provider.store.Load(ctx)
	if errors.Is(err, ErrCredentialsNotFound) {
		return "", ErrLoginRequired
	}
	if err != nil {
		return "", fmt.Errorf("reload authentication after lock: %w", err)
	}
	if !force && !TicketNeedsRefresh(credentials.Ticket, provider.now()) {
		return credentials.Ticket, nil
	}

	ticket, err := provider.refresher.Refresh(ctx, credentials.RefreshToken)
	if isTransientRefreshError(err) {
		if err := waitForRetry(ctx, provider.retryDelay); err != nil {
			return "", err
		}
		ticket, err = provider.refresher.Refresh(ctx, credentials.RefreshToken)
	}
	if err != nil {
		var refreshError *RefreshError
		if errors.As(err, &refreshError) && refreshError.Kind == RefreshFailureInvalid {
			if deleteErr := provider.store.Delete(ctx); deleteErr != nil {
				return "", fmt.Errorf("clear rejected authentication: %w", deleteErr)
			}
			return "", ErrLoginRequired
		}
		return "", err
	}
	credentials.Ticket = ticket
	if err := provider.store.Save(ctx, credentials); err != nil {
		return "", fmt.Errorf("save refreshed authentication: %w", err)
	}
	return ticket, nil
}

func isTransientRefreshError(err error) bool {
	var refreshError *RefreshError
	return errors.As(err, &refreshError) && refreshError.Kind == RefreshFailureTransient
}

func waitForRetry(ctx context.Context, delay time.Duration) error {
	if delay == 0 {
		return nil
	}
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}
