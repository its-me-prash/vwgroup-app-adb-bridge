<h1 align="center">VW Group App ADB Bridge</h1>

<p align="center">
  <strong>Home Assistant add-on that lets the <a href="https://github.com/its-me-prash/vwgroup-connect-ha">VW Group Connect</a> companion channel drive the brand app on a modern Android phone.</strong><br>
  <em>Bundles the real <code>adb</code> binary so it can pair with and connect over Android 11+ wireless debugging (TLS) — which the integration's pure-python transport cannot do — and exposes a small local API the integration talks to.</em>
</p>

<p align="center">
  <a href="https://github.com/sponsors/its-me-prash"><img src="https://img.shields.io/badge/%E2%9D%A4%20Sponsor-ec6cb9?logo=github-sponsors&logoColor=white" alt="Sponsor this project"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL%20v3-blue.svg" alt="License"></a>
  <a href="https://www.home-assistant.io"><img src="https://img.shields.io/badge/Home%20Assistant-Add--on-blue" alt="Home Assistant Add-on"></a>
</p>

---

## Why this exists

The VW Group Connect companion channel drives the official brand app on a spare Android phone over ADB and reads the values off the screen. Its transport is pure Python (`adb-shell`), which speaks only classic ADB — the RSA-key flow on a plain port like `5555`. It cannot talk to Android 11+ **wireless debugging**, which uses a TLS-encrypted port plus a pairing step (`adb pair` with a 6-digit code). On a modern phone the connection just fails with `InvalidCommandError`: the phone answers in TLS and the classic client cannot parse it.

The fix has to be the real `adb` binary, and a Home Assistant custom integration cannot ship one (it would need a per-architecture native binary). An add-on can. This add-on bundles `adb`, does the pairing and TLS itself, and exposes a tiny local HTTP API. The integration keeps everything else — the per-brand screen maps, the parsing, the commands — and just sends its shell commands here instead of straight to the phone.

## Requirements

- Home Assistant **OS** or **Supervised** (add-ons do not run on Container or Core).
- The [VW Group Connect](https://github.com/its-me-prash/vwgroup-connect-ha) integration.
- A spare Android phone on the same network, signed into the brand app, with wireless debugging available.

> For a phone you leave running as a permanent companion, an older phone (Android 10 or earlier) is the simpler choice — it exposes persistent classic ADB and works with the integration directly, no add-on needed. This add-on is for using a modern (Android 11+) phone.

## Install

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add:
   `https://github.com/its-me-prash/vwgroup-app-adb-bridge`
2. Install **VW Group App ADB Bridge** from the store and open its **Configuration** tab.

## Configure

On the phone: **Developer options → Wireless debugging → On**.

- **Pair device with pairing code** shows a pairing `IP:PORT` and a 6-digit code (valid for about a minute).
- The main wireless-debugging screen shows the connect `IP:PORT` (a different, higher port).

Fill in the options, then start the add-on (it pairs on start, within the pairing window):

| Option | Value |
|---|---|
| `pair_address` | the pairing `IP:PORT` |
| `pair_code` | the 6-digit code |
| `connect_address` | the connect `IP:PORT` |
| `api_token` | a secret the integration sends in the `X-Token` header |

The pairing key is kept under the add-on's `/data`, so once paired the phone keeps trusting it across restarts.

## Verify

The add-on **Log** shows the pairing and connection. From the HA host, or any machine on the network:

```bash
curl http://HOST_IP:8129/health
```

`"connected": true` with a `serial` means the phone is reachable. A real command on the phone:

```bash
curl -XPOST -H "X-Token: YOUR_SECRET" --data "echo ok" http://HOST_IP:8129/shell
```

## How it works

- **Add-on** — keeps the `adb` connection to the phone alive and serves `GET /health` and `POST /shell` (a shell command in, its output back).
- **Integration** — sends its existing companion commands (`uiautomator dump`, `input tap`, …) to `/shell` instead of over its own transport. Nothing else about the companion channel changes.

## Status

Experimental, paired with the experimental companion channel in the integration. It changes nothing for anyone not using that channel.

## Security

The `/shell` endpoint runs shell commands on the paired phone, so it is protected by the `api_token` you set. Keep the add-on on a trusted network. Please report security issues privately — see [SECURITY.md](SECURITY.md).

## License

[GNU AGPL v3.0-or-later](LICENSE). Attribution and name/trademark terms follow the main project — see its [ATTRIBUTION.md](https://github.com/its-me-prash/vwgroup-connect-ha/blob/main/ATTRIBUTION.md).
