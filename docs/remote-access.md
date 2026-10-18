# Remote access to the Ventuno Q (team)

Board: Arduino Ventuno Q `QCVENTUNO015`, Ubuntu 24.04 aarch64, 14 GiB RAM, Qualcomm QCS8275 + Hexagon NPU.
Venue Wi-Fi has client isolation, so plain `ssh user@<board-ip>` and `team-ventuno.local` do **not** work. We use Tailscale instead.

## Status (17 Oct 2026)

- Tailscale 1.104.1 installed and logged in on the board. Hostname `team-ventuno`, IP `100.74.60.29`, Tailscale SSH enabled. Owner: @jednhk.
- `sshd` active. Users created: `jed`, `dollar`, `lohith` (groups `video,render,dialout,plugdev,fastrpc` for NPU/camera/serial; no sudo).
- Temporary passwords: `changeme-<username>`; you are forced to change it on first login (Tailscale SSH does not ask for it; it is only for `sudo`-less local use / adb fallback).
- Tailnet policy: board tagged `tag:board` (owner `autogroup:admin`); SSH rule `src: autogroup:member -> dst: tag:board, users: jed, dollar, lohith, arduino`. Tailscale requires a *tag* as SSH destination for devices you don't own; a user or IP `dst` is rejected. Verified 17 Oct: all three users log in without passwords.

## Teammates: join once

1. Ask Jed to invite your email at https://login.tailscale.com/admin/users (free plan, 3 users).
2. Install Tailscale on your laptop (https://tailscale.com/download) and sign in to that invite.
3. Connect:
   ```sh
   ssh <you>@team-ventuno          # Tailscale SSH, no keys needed
   # or
   ssh <you>@100.74.60.29
   ```
4. First time: change your password when prompted, then
   ```sh
   git clone <repo-url> && cd ProjectDjoker
   python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
   ```
5. NPU / ExecuTorch env (every shell):
   ```sh
   export LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib
   export ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"
   ```
   Shared read-only assets: `/home/arduino/models` (pose `.pte`s, gemma3-1b, MediaPipe/RTMPose QNN bins), `/home/arduino/git/executorch` (runners under `build-x86/` and `build-xnnpack/`).

## Copy files

```sh
scp clip.mp4 <you>@team-ventuno:~/
scp -r <you>@team-ventuno:~/out ./out
```

## Etiquette

- **One person runs NPU jobs at a time.** Say so in the team chat before benchmarking; concurrent runs still work but timings become meaningless.
- Don't touch `/home/arduino`, Wi-Fi, or Tailscale config. Don't reboot without asking.
- Board internet: apt needs `-o Acquire::ForceIPv4=true -o Acquire::Retries=5` (IPv6 times out) and requires `arduino` sudo, so ask Jed for installs.

## Fallback for the laptop with the USB cable (Jed)

```sh
adb forward tcp:2222 tcp:22
ssh -p 2222 arduino@localhost     # or `ssh ventuno`, see docs/ventuno-ssh.md
```
