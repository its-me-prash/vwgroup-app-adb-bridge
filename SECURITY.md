# Security Policy

## Reporting a vulnerability

Please report security issues privately, not in a public issue. Use GitHub's
**Report a vulnerability** button (Security tab) on this repository, or the same
channel as the main [VW Group Connect](https://github.com/its-me-prash/vwgroup-connect-ha)
project.

## Scope notes

This add-on exposes a local HTTP API (`/health`, `/shell`) that runs shell
commands on the paired phone. Keep in mind:

- `POST /shell` is protected by the `api_token` you configure. Set one, and keep
  the add-on on a trusted network segment.
- The add-on pairs with, and holds a trusted ADB key for, the phone you connect.
  Anyone able to reach the API and present the token can run commands on that
  phone. Treat the token like a password.
- The add-on does not send anything off your network on its own; it only talks
  to the phone you paired and answers the integration's local requests.
