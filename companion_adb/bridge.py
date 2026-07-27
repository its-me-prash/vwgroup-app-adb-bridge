#!/usr/bin/env python3
# Copyright 2026 Prash Balan (@its-me-prash) — GNU AGPL v3.0-or-later
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ADB bridge for the VW Group App ADB Bridge add-on.

Why this add-on exists: the integration's pure-python transport (adb-shell)
speaks only classic ADB and CANNOT talk to Android 11+ "wireless debugging"
(TLS + pairing). This add-on bundles the real ``adb`` binary — which does the
pairing + TLS — and exposes a tiny token-protected HTTP API the integration
calls to run shell commands (``uiautomator dump``, ``input tap``, …). All the
screen-parsing / preset logic stays in the integration; this is only transport.

It pairs once (from config), then keeps a live connection to the phone. The
wireless-debugging connect port is ephemeral (it changes on every toggle/reboot),
so the add-on finds the current one over mDNS (``_adb-tls-connect._tcp``) instead
of a fixed address; ``connect_address`` is only a fallback. It serves:
  GET  /health  -> {connected, serial, adb_version, last_error, discovery}
  POST /shell   -> body is a shell command; runs it on the phone, returns stdout
                   (requires the X-Token header when api_token is set)

The ``uiautomator dump`` output comes back in the HTTP response, not the log.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from zeroconf import ServiceBrowser, Zeroconf
except Exception:  # noqa: BLE001 - discovery is optional; fall back to config
    ServiceBrowser = None  # type: ignore[assignment]
    Zeroconf = None  # type: ignore[assignment]

_OPTIONS_PATH = "/data/options.json"
_LISTEN_PORT = 8129
_ADB_MDNS_TYPE = "_adb-tls-connect._tcp.local."

_state: dict[str, object] = {
    "connected": False,
    "serial": None,
    "adb_version": "",
    "last_error": "",
    "discovery": "off",
}
_discovered: dict[str, str] = {}  # mDNS name -> "ip:port"
_lock = threading.Lock()


def _log(msg: str) -> None:
    print(f"[companion-adb] {msg}", flush=True)


def _options() -> dict:
    try:
        with open(_OPTIONS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _adb(*args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb", *args], capture_output=True, text=True, timeout=timeout, check=False,
    )


def _set(**kw: object) -> None:
    with _lock:
        _state.update(kw)


# ── mDNS discovery of the current wireless-debugging endpoint ────────────────

class _AdbListener:
    def _record(self, zc: object, type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name, timeout=2000)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        addrs = info.parsed_addresses() if info else []
        if info and addrs:
            addr = f"{addrs[0]}:{info.port}"
            if _discovered.get(name) != addr:
                _discovered[name] = addr
                _log(f"discovered phone at {addr} (mDNS)")

    def add_service(self, zc: object, type_: str, name: str) -> None:
        self._record(zc, type_, name)

    def update_service(self, zc: object, type_: str, name: str) -> None:
        self._record(zc, type_, name)

    def remove_service(self, zc: object, type_: str, name: str) -> None:
        _discovered.pop(name, None)


def _start_discovery() -> None:
    if Zeroconf is None:
        _set(discovery="unavailable")
        _log("zeroconf not installed — using the configured connect_address only")
        return
    try:
        zc = Zeroconf()
        ServiceBrowser(zc, _ADB_MDNS_TYPE, _AdbListener())  # keep the browser alive
        _set(discovery="on")
        _log("mDNS discovery running")
    except Exception as err:  # noqa: BLE001
        _set(discovery="error")
        _log(f"mDNS discovery could not start: {err}")


def _candidates(fallback: str) -> list[str]:
    """Addresses to try, current mDNS-discovered ones first, then the fallback."""
    out = list(dict.fromkeys(_discovered.values()))
    if fallback and fallback not in out:
        out.append(fallback)
    return out


# ── adb pair / connect ───────────────────────────────────────────────────────

def _pair(addr: str, code: str) -> None:
    if not addr or not code:
        _log("no pairing code configured — skipping the pair step "
             "(fine if the phone already trusts this add-on)")
        return
    _log(f"pairing with {addr} ...")
    try:
        r = _adb("pair", addr, code, timeout=60)
    except Exception as err:  # noqa: BLE001
        _log(f"pair failed: {err}")
        _set(last_error=f"pair exception: {err}")
        return
    out = (r.stdout + " " + r.stderr).strip()
    if "successfully paired" in out.lower() or "already" in out.lower():
        _log("paired OK")
        _set(last_error="")
    else:
        _log(f"pair result: {out}")
        _set(last_error=f"pair: {out}")


def _connect(addr: str) -> bool:
    try:
        r = _adb("connect", addr, timeout=30)
    except Exception as err:  # noqa: BLE001
        _set(last_error=f"connect exception: {err}")
        return False
    out = (r.stdout + " " + r.stderr).lower()
    if "connected to" in out or "already connected" in out:
        return True
    _set(last_error=f"connect {addr}: {(r.stdout + ' ' + r.stderr).strip()}")
    return False


def _online_serial() -> str | None:
    """A phone adb currently has in 'device' state (any port), or None."""
    try:
        devs = _adb("devices", timeout=10).stdout
    except Exception:  # noqa: BLE001
        return None
    for line in devs.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def _maintain(opts: dict) -> None:
    try:
        ver = _adb("version", timeout=10).stdout.splitlines()[0]
    except Exception:  # noqa: BLE001
        ver = "?"
    _set(adb_version=ver)
    _log(f"using {ver}")
    _pair(str(opts.get("pair_address", "")), str(opts.get("pair_code", "")))
    fallback = str(opts.get("connect_address", "")).strip()
    was: bool | None = None
    while True:
        serial = _online_serial()
        if serial is None:
            for addr in _candidates(fallback):
                if _connect(addr):
                    break
            serial = _online_serial()
        connected = serial is not None
        if connected:
            _set(connected=True, serial=serial, last_error="")
        else:
            _set(connected=False, serial=None)
            if not _state.get("last_error"):
                _set(last_error="no phone found (is wireless debugging on and the "
                                "phone awake?)")
        if connected != was:
            _log(f"connected: {serial}" if connected else "no phone connected")
            was = connected
        time.sleep(15)


# ── HTTP API ─────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        token = str(_options().get("api_token", ""))
        return not token or self.headers.get("X-Token", "") == token

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            with _lock:
                self._reply(200, dict(_state))
            return
        self._reply(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/shell":
            self._reply(404, {"error": "not found"})
            return
        if not self._auth_ok():
            _log("rejected /shell: bad or missing token")
            self._reply(403, {"error": "bad or missing token"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        cmd = self.rfile.read(length).decode()
        with _lock:
            serial = _state.get("serial")
        if not serial:
            self._reply(503, {"error": "phone not connected"})
            return
        try:
            r = _adb("-s", str(serial), "shell", cmd, timeout=30)
            _log(f"shell rc={r.returncode}: {cmd[:80]}")
            self._reply(200, {"stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode})
        except Exception as err:  # noqa: BLE001
            _log(f"shell error: {cmd[:80]} :: {err}")
            self._reply(500, {"error": str(err)})

    def log_message(self, *_a: object) -> None:  # keep the default request log quiet
        return


def main() -> None:
    opts = _options()
    _start_discovery()
    threading.Thread(target=_maintain, args=(opts,), daemon=True).start()
    httpd = ThreadingHTTPServer(("0.0.0.0", _LISTEN_PORT), _Handler)
    _log(f"bridge listening on :{_LISTEN_PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
