# VW Group App ADB Bridge

Bundles the real `adb` binary and does the Android 11+ **pairing + TLS** that the
[VW Group Connect](https://github.com/its-me-prash/vwgroup-connect-ha)
integration's pure-python transport cannot. It exposes a small local HTTP API the
integration talks to, so its companion channel can drive the brand app on a
modern Android phone. Experimental.

## 1. Configure and start

In the add-on **Configuration** tab, set:

- `api_token` — a secret string (the integration sends it in the `X-Token` header)
- `pair_code` — leave blank for now; you fill it in the next step

**Save**, then **Start** the add-on. The bridge finds the phone over mDNS by
itself, so the addresses stay blank on a normal network.

## 2. Pair the phone (Android 11+, one time)

On the phone: Developer options → **Wireless debugging** → On → tap
**"Pair device with pairing code"**. It shows a **6-digit code** (and a pairing
`IP:PORT` you do not need).

While that dialog is open, put the **6-digit code** into `pair_code` and **Save**.
The add-on discovers the pairing endpoint over mDNS and pairs within a few
seconds — you do not enter any address. After it pairs, the phone trusts the
add-on across restarts, so you can clear `pair_code` again.

Two different endpoints are involved and the add-on handles both: the **pairing**
port (only open while that dialog is up) and the **connect** port (the main
Wireless debugging screen). Pairing against the connect port is what fails with
"protocol fault", which is why the code alone is the reliable path.

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

- `GET /health` — `{connected, serial, paired, adb_version, last_error, discovery}`
- `POST /shell` — request body is a shell command; runs it on the phone and returns
  `{stdout, stderr, rc}`. Requires the `X-Token` header when `api_token` is set.

## Notes

- The pairing key is kept under `/data`, so once paired the phone keeps trusting the
  add-on across restarts.
- The connect port is ephemeral (it changes on every toggle/reboot); the add-on
  re-finds it over mDNS, so you do not have to update anything.
- Host networking is required (to reach the phone on the LAN and see its mDNS
  advertisements), and it is set for you.
