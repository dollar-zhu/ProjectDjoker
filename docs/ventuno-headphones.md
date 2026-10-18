# Ventuno headphones with a Mac camera worker

The live worker can remain on the Mac while Piper synthesis and Bluetooth playback
run on the Ventuno. `audio.remote_url` selects the board service; without it,
the existing local `BluetoothRoute` and `Speaker` remain unchanged.

On the board, copy `live/__init__.py`, `audio.py`, `bluetooth.py`, and
`remote_audio.py` into a directory containing `live/`. Run as the normal audio
user, with that user's PipeWire session:

```sh
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
python -m live.remote_audio --address YOUR_HEADSET_MAC --voice /absolute/voice.onnx
```

The service binds only `127.0.0.1:18877`. Forward it over the existing USB link:

```sh
adb -s YOUR_BOARD_SERIAL forward tcp:18877 tcp:18877
```

Set `DJOKER_AUDIO_CONFIG` for the Mac web server to a private JSON file:

```json
{
  "audio": {
    "backend": "piper",
    "remote_url": "http://127.0.0.1:18877",
    "bluetooth_address": "YOUR_HEADSET_MAC"
  },
  "conversation": {"enabled": true, "cooldown_s": 12},
  "asr": {"enabled": false},
  "led": {"backend": "browser"}
}
```

The address must match the service's selected headset. There is no Mac-speaker
fallback. Mute, stop and cancellation forward the current utterance ID; the board
also rejects a cancelled request that arrives late. The board caches the Piper
voice and greeting. Speech text is not logged by the HTTP server. This is a
local USB service, not an authenticated network API; do not expose its port.

For the current Ubuntu 24.04 / WirePlumber 0.4.17 board, headless Bluetooth needed
two per-user overrides: `bluez_monitor.enabled = false` for GDM, and
`bluez_monitor.properties["with-logind"] = false` for the `arduino` user.
Both live under the respective user's `.config/wireplumber/bluetooth.lua.d/`.
Restart those users' WirePlumber services after changing them. Do not copy this
Lua configuration to WirePlumber 0.5.

Current deployment uses the `arduino` user service `djoker-audio.service`, code
under `/home/arduino/djoker-audio`, and the existing Lessac Piper voice. Recreate
the ADB forward after reconnecting USB. The Mac's private configuration and
reconnect helper are under `local/audio/` and are intentionally ignored by Git.

Verify `GET /status` reports the selected address and `audio_ready: true`, then
confirm speech is audible in the headphones. The live conversation currently
speaks framing prompts and approved dialogue; it does not automatically narrate
the saved review's generated coaching. ASR remains a separately configured feature.

Rollback: remove `audio.remote_url` or unset `DJOKER_AUDIO_CONFIG`, stop/disable
the board's `djoker-audio` user service, and remove the ADB port forward. To restore
desktop-only Bluetooth ownership, remove the two override files and restart
the affected WirePlumber user services.
