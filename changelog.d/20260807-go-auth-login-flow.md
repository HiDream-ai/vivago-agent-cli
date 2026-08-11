## Added

- Add the Go login coordinator for the dedicated `/agent/login` browser flow, including a random loopback callback port, one-time state validation, five-minute timeout, manual URL fallback, and secure credential persistence.
- Add credential-safe authentication status and local logout services for future Go CLI command wiring.

## Fixed

- Finish writing the browser callback success page before the CLI closes the loopback listener.
