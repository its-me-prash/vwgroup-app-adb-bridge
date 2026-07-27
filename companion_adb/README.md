# VW Group App ADB Bridge

Bundles the real `adb` binary and does the Android 11+ **pairing + TLS** that the
[VW Group Connect](https://github.com/its-me-prash/vwgroup-connect-ha)
integration's pure-python transport cannot. It exposes a small local HTTP API the
integration talks to, so its companion channel can drive the brand app on a
modern Android phone. Experimental.

## 1. On the phone (Android 11+)

Developer options → **Wireless debugging** → On.

- Tap **"Pair device with pairing code"** — note the **pairing** `IP:PORT` and the
  **6-digit code** (this dialog is valid for about a minute).
- On the main Wireless debugging screen, note the **connect** `IP:PORT`
  (a different, higher port).

## 2. Configure and start

In the add-on **Configuration** tab, set:

- `pair_address` — the pairing `IP:PORT`
- `pair_code` — the 6-digit code
- `connect_address` — the connect `IP:PORT`
- `api_token` — a secret string (the integration sends it in the `X-Token` header)

**Timing:** open the phone's pairing dialog, quickly fill these in, **Save**, then
**Start** the add-on (it pairs on start, within the one-minute window).

## 3. Check it worked

The add-on **Log** shows the pairing and connection. Then, from the HA host or any
machine on the network:

```bash
curl http://HOST_IP:8129/health
```

Expect `"connected": true`, a `serial`, and an `adb_version`. A real command on the
phone:

```bash
curl -XPOST -H "X-Token: YOUR_SECRET" --data "echo ok" http://HOST_IP:8129/shell
```

## API

- `GET /health` — `{connected, serial, adb_version, last_error}`
- `POST /shell` — request body is a shell command; runs it on the phone and returns
  `{stdout, stderr, rc}`. Requires the `X-Token` header when `api_token` is set.

## Notes

- The pairing key is kept under `/data`, so once paired the phone keeps trusting the
  add-on across restarts.
- The connect port changes after a phone reboot; update `connect_address` when it
  does. Automatic discovery is planned.
- Host networking is required (to reach the phone on the LAN), and it is set for you.
