# Changelog

All notable changes to this add-on are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning: [Semantic Versioning](https://semver.org/).

## [0.1.0-beta.10] - 2026-08-01

### Changed
- Documented how to point VW Group Connect at this add-on. The integration
  gained an option to run its companion channel through this bridge in v2.27.0,
  which is what makes an Android 11+ phone work; the setup steps are in the
  README.

## [0.1.0-beta.9] - 2026-07-28

### Added
- An add-on icon and logo, so it shows its own artwork in the Home Assistant
  store list and on the add-on page instead of the default placeholder.

## [0.1.0-beta.8] - 2026-07-28

### Fixed
- Pairing now uses the phone's pairing endpoint, not the connect endpoint.
  Android 11+ advertises two separate wireless-debugging services over mDNS:
  `_adb-tls-pairing._tcp` (the pairing dialog, a transient port) and
  `_adb-tls-connect._tcp` (the connect port). `adb pair` against the connect
  port fails with "protocol fault (couldn't read status message)". The add-on
  now discovers the pairing endpoint over mDNS as well.

### Changed
- You normally enter only the 6-digit `pair_code`. Open the phone's "Pair device
  with pairing code" dialog, put the code in, save, and the add-on finds the
  pairing address itself and pairs within a few seconds. `pair_address` and
  `connect_address` are optional fallbacks for networks where mDNS does not work.
- `/health` now also reports `paired` and `discovery`, and pairing is retried on
  a faster poll while the dialog is open.
- Hardened the maintain loop: the mDNS discovery tables are read and written
  under a lock and the loop survives transient errors, so an mDNS update landing
  mid-iteration can no longer stop the bridge. Each pairing endpoint is tried
  once per run to keep the log clean.

## [0.1.0-beta.7] - 2026-07-28

### Fixed
- The changelog now ships inside the add-on directory, so Home Assistant renders
  it in the add-on and update views. It previously lived only in the repository
  root, which the Supervisor does not read, so the update dialog showed
  "No changelog found for app".

## [0.1.0-beta.6] - 2026-07-28

### Fixed
- Removed the AppArmor profile added in beta.5: it was too strict for the
  s6-overlay init and put the container in a restart loop (`can't open '/init'`).
  The security rating goes back to 4; a properly tested profile (or the ingress
  web UI, which lifts the rating on its own) can revisit this later. Working beats
  a broken container for one rating point.

## [0.1.0-beta.5] - 2026-07-28

### Added
- An AppArmor profile that confines the container (allows adb, python, the s6
  init system, network and the data volume; denies the rest). This raises the
  Home Assistant add-on security rating. `host_network` stays (it is required
  for adb over the LAN and mDNS), so the rating cannot reach the very top without
  the ingress web UI planned for QR pairing.

## [0.1.0-beta.4] - 2026-07-28

### Added
- mDNS auto-discovery of the wireless-debugging endpoint. The connect port is
  ephemeral (it changes on every toggle or reboot), so the add-on now finds the
  current one over `_adb-tls-connect._tcp` instead of a fixed address.
  `connect_address` becomes an optional fallback (leave it blank). Best-effort:
  if `py3-zeroconf` is unavailable the add-on falls back to `connect_address`.

### Changed
- `ADB_MDNS_AUTO_CONNECT=1` so adb itself also re-finds the phone; the served
  device is now whichever phone adb has online, so a port change no longer needs
  a manual update.

## [0.1.0-beta.3] - 2026-07-28

### Changed
- The add-on log now shows the pairing, the connection state, and each shell
  command it runs, so the log is useful for troubleshooting. (The `uiautomator
  dump` output still comes back in the HTTP response, not the log.)

## [0.1.0-beta.2] - 2026-07-27

### Added
- `build.yaml` pinning the base image to `ghcr.io/home-assistant/{arch}-base:3.21`,
  so the bundled `adb` is a known, reproducible version rather than whatever the
  default base ships. Added `armhf` and `i386` to the supported arches.

### Changed
- `startup: services` and `boot: manual` (the add-on runs as a service and you
  start it yourself; it does not auto-start on a Home Assistant reboot).

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
