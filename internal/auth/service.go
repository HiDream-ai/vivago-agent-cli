package auth

import (
	"context"
	"errors"
	"fmt"
	"time"
)

type Status struct {
	LoggedIn     bool   `json:"logged_in"`
	Backend      string `json:"backend"`
	NeedsRefresh bool   `json:"needs_refresh"`
}

type Service struct {
	store CredentialStore
	now   func() time.Time
}

func NewService(store CredentialStore, now func() time.Time) *Service {
	if now == nil {
		now = time.Now
	}
	return &Service{store: store, now: now}
}

func (service *Service) Status(ctx context.Context) (Status, error) {
	credentials, err := service.store.Load(ctx)
	if errors.Is(err, ErrCredentialsNotFound) {
		return Status{Backend: service.store.Backend()}, nil
	}
	if err != nil {
		return Status{}, fmt.Errorf("load authentication status: %w", err)
	}
	return Status{
		LoggedIn:     true,
		Backend:      service.store.Backend(),
		NeedsRefresh: TicketNeedsRefresh(credentials.Ticket, service.now()),
	}, nil
}

func (service *Service) Logout(ctx context.Context) error {
	if err := service.store.Delete(ctx); err != nil {
		return fmt.Errorf("delete local authentication: %w", err)
	}
	return nil
}
