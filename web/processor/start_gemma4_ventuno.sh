#!/bin/sh
# Run on the Mac. The server binds only to Ventuno's loopback interface.
set -eu
serial=${DJOKER_SERIAL:-242692658}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
adb -s "$serial" shell 'mkdir -p /home/arduino/.config/systemd/user'
adb -s "$serial" push "$script_dir/djoker-gemma4.service" /home/arduino/.config/systemd/user/djoker-gemma4.service
adb -s "${DJOKER_SERIAL:-242692658}" shell '
set -eu
base=/home/arduino/djoker-gemma4
test -x "$base/runtime/bin/ollama"
test -f "$base/models/manifests/registry.ollama.ai/library/gemma4/e2b"
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
systemctl --user daemon-reload
systemctl --user enable --now djoker-gemma4.service
attempt=0
until curl -fsS --max-time 2 http://127.0.0.1:11434/api/version; do
  attempt=$((attempt + 1))
  test "$attempt" -lt 10
  sleep 1
done
'
