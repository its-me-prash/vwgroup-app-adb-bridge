# Changelog

All notable changes to this add-on are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning: [Semantic Versioning](https://semver.org/).

## [0.1.0-beta.1] - 2026-07-27

First beta. A proof of concept, paired with the experimental companion channel in
[VW Group Connect](https://github.com/its-me-prash/vwgroup-connect-ha). Not yet
confirmed end-to-end against a real phone.

### Added
- ADB-over-TLS bridge: bundles the real `adb` binary, pairs with an Android 11+
  phone over wireless debugging (pairing code + TLS), and keeps the connection
  alive. The pairing key persists under `/data`, so the phone keeps trusting the
  add-on across restarts.
- Local HTTP API for the integration: `GET /health` and a token-protected
  `POST /shell`.
- Multi-arch (amd64 / aarch64 / armv7), host networking for the LAN, and a
  persistent adb key.

### Known limitations
- Pairing is entered manually; QR pairing is planned (see [ROADMAP.md](ROADMAP.md)).
- The connect port changes after a phone reboot; update `connect_address` when it
  does. Automatic discovery is planned.
