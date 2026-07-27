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

Android 11+ advertises TWO wireless-debugging endpoints over mDNS, on separate
ephemeral ports:
  ``_adb-tls-pairing._tcp``  the pairing port, advertised ONLY while the phone's
                             "Pair device with pairing code" dialog is open.
  ``_adb-tls-connect._tcp``  the connect port, advertised while wireless
                             debugging is on.
``adb pair`` must go to the pairing port and ``adb connect`` to the connect port
— pairing against the connect port fails with "protocol fault". The add-on finds
both over mDNS, so you only enter the 6-digit code; the addresses are optional
fallbacks. It serves:
  GET  /health  -> {connected, serial, paired, adb_version, last_error, discovery}
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
_ADB_CONNECT_TYPE = "_adb-tls-connect._tcp.local."
_ADB_PAIR_TYPE = "_adb-tls-pairing._tcp.local."

_state: dict[str, object] = {
    "connected": False,
    "serial": None,
    "paired": False,
    "adb_version": "",
    "last_error": "",
    "discovery": "off",
}
_connect_addrs: dict[str, str] = {}  # mDNS name -> "ip:port" (wireless-debugging)
_pair_addrs: dict[str, str] = {}     # mDNS name -> "ip:port" (pairing dialog, transient)
_lock = threading.Lock()
_disc_lock = threading.Lock()  # guards the two discovery dicts (zeroconf threads mutate them)


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


# ── mDNS discovery of the current wireless-debugging endpoints ───────────────

class _AdbListener:
    """Records ip:port for one mDNS service type into the given store."""

    def __init__(self, store: dict[str, str], label: str) -> None:
        self._store = store
        self._label = label

    def _record(self, zc: object, type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name, timeout=2000)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        addrs = info.parsed_addresses() if info else []
        if info and addrs:
            addr = f"{addrs[0]}:{info.port}"
            with _disc_lock:
                changed = self._store.get(name) != addr
                if changed:
                    self._store[name] = addr
            if changed:
                _log(f"discovered {self._label} endpoint at {addr} (mDNS)")

    def add_service(self, zc: object, type_: str, name: str) -> None:
        self._record(zc, type_, name)

    def update_service(self, zc: object, type_: str, name: str) -> None:
        self._record(zc, type_, name)

    def remove_service(self, zc: object, type_: str, name: str) -> None:
        with _disc_lock:
            self._store.pop(name, None)


def _start_discovery() -> None:
    if Zeroconf is None:
        _set(discovery="unavailable")
        _log("zeroconf not installed — using the configured addresses only")
        return
    try:
        zc = Zeroconf()
        # Keep both browsers alive for the process lifetime.
        ServiceBrowser(zc, _ADB_CONNECT_TYPE, _AdbListener(_connect_addrs, "connect"))
        ServiceBrowser(zc, _ADB_PAIR_TYPE, _AdbListener(_pair_addrs, "pairing"))
        _set(discovery="on")
        _log("mDNS discovery running (connect + pairing)")
    except Exception as err:  # noqa: BLE001
        _set(discovery="error")
        _log(f"mDNS discovery could not start: {err}")


def _candidates(store: dict[str, str], fallback: str) -> list[str]:
    """Discovered addresses first (deduped), then the configured fallback.

    Snapshots the store under the lock: zeroconf callback threads mutate it, and
    iterating it directly could raise 'dictionary changed size during iteration'.
    """
    with _disc_lock:
        vals = list(store.values())
    out = list(dict.fromkeys(vals))
    if fallback and fallback not in out:
        out.append(fallback)
    return out


# ── adb pair / connect ───────────────────────────────────────────────────────

def _pair(addr: str, code: str) -> bool:
    """Pair against a pairing endpoint. Returns True on success/already paired."""
    if not addr or not code:
        return False
    _log(f"pairing with {addr} ...")
    try:
        r = _adb("pair", addr, code, timeout=60)
    except Exception as err:  # noqa: BLE001
        _log(f"pair failed: {err}")
        _set(last_error=f"pair exception: {err}")
        return False
    out = (r.stdout + " " + r.stderr).strip()
    if "successfully paired" in out.lower() or "already paired" in out.lower():
        _log("paired OK")
        _set(last_error="", paired=True)
        return True
    _log(f"pair result: {out}")
    _set(last_error=f"pair: {out}")
    return False


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

    pair_code = str(opts.get("pair_code", "")).strip()
    pair_fallback = str(opts.get("pair_address", "")).strip()
    connect_fallback = str(opts.get("connect_address", "")).strip()
    paired = False
    attempted_pairs: set[str] = set()  # each pairing endpoint is tried once per run
    was: bool | None = None
    while True:
        connected = False
        try:
            serial = _online_serial()
            if serial is None:
                # Pair first if a code is set and we have not paired yet. The
                # pairing endpoint is advertised only while the phone's pairing
                # dialog is open, so we wait for mDNS to see it. Each endpoint is
                # tried once: re-pairing the same address with the same (fixed,
                # startup-read) code just fails again and spams the log.
                if pair_code and not paired:
                    for paddr in _candidates(_pair_addrs, pair_fallback):
                        if paddr in attempted_pairs:
                            continue
                        attempted_pairs.add(paddr)
                        if _pair(paddr, pair_code):
                            paired = True
                            break
                for addr in _candidates(_connect_addrs, connect_fallback):
                    if _connect(addr):
                        break
                serial = _online_serial()
            connected = serial is not None
            if connected:
                _set(connected=True, serial=serial, last_error="")
            else:
                _set(connected=False, serial=None)
                if not _state.get("last_error"):
                    if pair_code and not paired:
                        _set(last_error="waiting for the phone's pairing dialog — open "
                                        "'Pair device with pairing code' on the phone")
                    else:
                        _set(last_error="no phone found (is wireless debugging on and "
                                        "the phone awake?)")
            if connected != was:
                _log(f"connected: {serial}" if connected else "no phone connected")
                was = connected
        except Exception as err:  # noqa: BLE001 - a transient error must not kill the thread
            _log(f"maintain loop error (continuing): {err}")
            _set(last_error=f"maintain: {err}")
        # Poll quickly while the pairing dialog is open (it times out), then
        # settle into a slower keepalive once we are paired or connected.
        time.sleep(5 if (pair_code and not paired and not connected) else 15)


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
