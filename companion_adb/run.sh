#!/usr/bin/env bash
# Persist adb's keypair under the add-on's /data volume so the phone keeps
# trusting us across restarts (pair once, reconnect forever). Then start the
# adb server and hand off to the bridge (pairs, connects, serves the HTTP API).
set -e
export HOME=/data
mkdir -p /data/.android
adb start-server >/dev/null 2>&1 || true
exec python3 /bridge.py
