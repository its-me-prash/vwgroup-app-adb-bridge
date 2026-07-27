# Roadmap

Where the VW Group App ADB Bridge and its companion channel in the
[VW Group Connect](https://github.com/its-me-prash/vwgroup-connect-ha) integration
are headed. Each phase is gated on the one before it.

## Phase 0 — Proof of concept (current)

Confirm the real `adb` inside this add-on can pair with and drive a modern
(Android 11+) phone over wireless debugging, and run `uiautomator dump`.
Everything below depends on this working.

## Phase 1 — Integration transport + attach to an existing car

- A transport in the integration that sends the companion channel's commands to
  this add-on's `/shell` API instead of speaking ADB directly. Nothing else about
  the companion channel changes.
- Attach to an existing vehicle: the integration keys every car's device on its
  VIN, so a companion entry with a car's VIN already merges its sensors and
  commands onto that car's device — no duplicate. The setup step will offer a
  dropdown of the vehicles you already have (by brand and model), so you pick the
  car instead of typing a VIN.

## Phase 2 — Auto-discovery

The add-on advertises itself to the Home Assistant Supervisor once a phone is
connected, so the integration offers to set up the companion channel on its own,
with no address or token to enter by hand.

## Phase 3 — QR pairing

A small page in the add-on shows a QR code. Scan it with Android's "Pair device
with QR code" and the add-on pairs over mDNS — no six-digit code to type.

## Phase 4 — Two cars in one app

Some brand apps show more than one vehicle (for example two Audis in myAudi). The
companion channel will switch between the cars in the app, read each one, and map
each to its VIN, so both land on their own existing car device. The simpler route,
if you prefer, is one spare phone per car: each is a separate companion entry and
both merge by VIN.
