#!/usr/bin/env python3
# Copyright 2026 Prash Balan (@its-me-prash) — GNU AGPL v3.0-or-later
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Minimal ADB bridge for the VAG Connect companion HA add-on (PoC).

Why this add-on exists: the integration's pure-python transport (adb-shell)
speaks only classic ADB and CANNOT talk to Android 11+ "wireless debugging"
(TLS + pairing). This add-on bundles the real ``adb`` binary — which does the
pairing + TLS — and exposes a tiny token-protected HTTP API the integration
calls to run shell commands (``uiautomator dump``, ``input tap``, …). All the
screen-parsing / preset logic stays in the integration; this is only transport.

PoC scope: pair once (from config), connect to the wireless-debugging address,
keep it alive, and serve:
  GET  /health  -> {connected, serial, adb_version, last_error}
  POST /shell   -> body is a shell command; runs it on the phone, returns stdout
                   (requires the X-Token header when api_token is set)
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_OPTIONS_PATH = "/data/options.json"
_LISTEN_PORT = 8129

_state: dict[str, object] = {
    "connected": False,
    "serial": None,
    "adb_version": "",
    "last_error": "",
}
_lock = threading.Lock()


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


def _pair(addr: str, code: str) -> None:
    if not addr or not code:
        return
    try:
        r = _adb("pair", addr, code, timeout=60)
    except Exception as err:  # noqa: BLE001
        _set(last_error=f"pair exception: {err}")
        return
    out = (r.stdout + r.stderr).lower()
    if "successfully paired" in out or "already" in out:
        _set(last_error="")
    else:
        _set(last_error=f"pair: {(r.stdout + ' ' + r.stderr).strip()}")


def _connect(addr: str) -> bool:
    try:
        r = _adb("connect", addr, timeout=30)
    except Exception as err:  # noqa: BLE001
        _set(connected=False, serial=None, last_error=f"connect exception: {err}")
        return False
    out = (r.stdout + r.stderr).lower()
    ok = "connected to" in out or "already connected" in out
    if ok:
        _set(connected=True, serial=addr, last_error="")
    else:
        _set(connected=False, serial=None,
             last_error=f"connect: {(r.stdout + ' ' + r.stderr).strip()}")
    return ok


def _device_ready(addr: str) -> bool:
    try:
        devs = _adb("devices", timeout=10).stdout
    except Exception:  # noqa: BLE001
        return False
    for line in devs.splitlines():
        if line.startswith(addr) and line.rstrip().endswith("device"):
            return True
    return False


def _maintain(opts: dict) -> None:
    try:
        _set(adb_version=_adb("version", timeout=10).stdout.splitlines()[0])
    except Exception:  # noqa: BLE001
        _set(adb_version="?")
    _pair(str(opts.get("pair_address", "")), str(opts.get("pair_code", "")))
    addr = str(opts.get("connect_address", "")).strip()
    while True:
        if addr:
            if _device_ready(addr):
                _set(connected=True, serial=addr)
            else:
                _connect(addr)
        time.sleep(15)


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
            self._reply(200, {"stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode})
        except Exception as err:  # noqa: BLE001
            self._reply(500, {"error": str(err)})

    def log_message(self, *_a: object) -> None:  # quiet
        return


def main() -> None:
    opts = _options()
    threading.Thread(target=_maintain, args=(opts,), daemon=True).start()
    httpd = ThreadingHTTPServer(("0.0.0.0", _LISTEN_PORT), _Handler)
    print(f"[companion-adb] bridge listening on :{_LISTEN_PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
