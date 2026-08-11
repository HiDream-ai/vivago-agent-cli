package auth

import (
	"crypto/subtle"
	"fmt"
	"net"
	"net/http"
	"strings"
	"sync/atomic"
)

const maxCallbackBodyBytes = 64 * 1024

type CallbackResult struct {
	Ticket       string
	RefreshToken string
}

type CallbackHandler struct {
	expectedState string
	result        chan CallbackResult
	consumed      atomic.Bool
}

func NewCallbackHandler(expectedState string) *CallbackHandler {
	return &CallbackHandler{
		expectedState: expectedState,
		result:        make(chan CallbackResult, 1),
	}
}

func (handler *CallbackHandler) Result() <-chan CallbackResult {
	return handler.result
}

func (handler *CallbackHandler) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	host, _, err := net.SplitHostPort(request.RemoteAddr)
	if err != nil || !net.ParseIP(host).IsLoopback() {
		http.Error(writer, "callback must come from loopback", http.StatusForbidden)
		return
	}
	if request.Method != http.MethodPost || request.URL.Path != "/callback" {
		http.Error(writer, "invalid callback request", http.StatusNotFound)
		return
	}
	request.Body = http.MaxBytesReader(writer, request.Body, maxCallbackBodyBytes)
	if err := request.ParseForm(); err != nil {
		http.Error(writer, "invalid callback form", http.StatusBadRequest)
		return
	}
	ticket := strings.TrimSpace(request.PostForm.Get("ticket"))
	refreshToken := strings.TrimSpace(request.PostForm.Get("refresh_token"))
	state := request.PostForm.Get("state")
	if ticket == "" || refreshToken == "" || state == "" {
		http.Error(writer, "invalid callback form", http.StatusBadRequest)
		return
	}
	if subtle.ConstantTimeCompare([]byte(state), []byte(handler.expectedState)) != 1 {
		http.Error(writer, "invalid callback state", http.StatusBadRequest)
		return
	}
	if !handler.consumed.CompareAndSwap(false, true) {
		http.Error(writer, "callback already used", http.StatusConflict)
		return
	}

	writer.Header().Set("Content-Type", "text/html; charset=utf-8")
	writer.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprint(writer, "<!doctype html><title>VivagoAgent CLI</title><p>Login completed. You can return to the terminal.</p>")
	handler.result <- CallbackResult{Ticket: ticket, RefreshToken: refreshToken}
}
