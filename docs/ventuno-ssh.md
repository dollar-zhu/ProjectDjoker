# SSH into the Ventuno Q

Board: Arduino Ventuno Q `QCVENTUNO015` (Qualcomm QCS8275, Ubuntu 24.04 aarch64). Linux user: `arduino`.

## TL;DR

```sh
adb forward tcp:2222 tcp:22   # once per USB plug-in / board reboot
ssh ventuno
```

`scp` works the same way:

```sh
scp clip.mp4 ventuno:~/
scp -r ventuno:~/out ./out
```

## Why not plain Wi-Fi SSH?

The board is on the venue Wi-Fi (last seen at `10.104.8.210`) and `sshd` is running and listening on `0.0.0.0:22` with no firewall. But the access point enforces **client isolation**: ARP between the Mac and the board stays `INCOMPLETE` in both directions, so `ping`, `nc`, and `ssh` all time out. Nothing on either host can fix that.

The board's USB gadget only exposes a serial console (`acm.GS0`) and ADB (`ffs.adb`), no RNDIS/NCM network interface, so USB networking isn't available either without root changes.

The workaround is to tunnel SSH through ADB over the USB cable.

## One-time setup (already done on jedng's Mac)

1. Confirm ADB sees the board:
   ```sh
   adb devices        # should list serial 242692658
   ```
2. Install your public key on the board (no password needed, ADB shell runs as `arduino`):
   ```sh
   cat ~/.ssh/id_ed25519.pub | adb shell 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
   ```
   If you have no key yet, run `ssh-keygen -t ed25519` first.
3. Add a host alias to `~/.ssh/config`:
   ```
   Host ventuno
     HostName localhost
     Port 2222
     User arduino
     IdentityFile ~/.ssh/id_ed25519
   ```

## Every session

```sh
adb forward tcp:2222 tcp:22
ssh -o BatchMode=yes ventuno hostname   # expect: QCVENTUNO015
```

ADB forwards do not persist across unplugging the cable, restarting the ADB server, or rebooting the board. If `ssh ventuno` hangs or says "connection refused", re-run the `adb forward` line.

Without the alias: `ssh -p 2222 arduino@localhost` and `scp -P 2222 file arduino@localhost:~/`.

## Other ways in

- `adb shell` — direct shell, no SSH needed. Good for quick checks.
- `adb push <local> <remote>` / `adb pull` — file transfer without SSH.
- Serial console: `/dev/cu.usbmodem2426926582` (e.g. `screen /dev/cu.usbmodem2426926582 115200`).

## Alternatives if you need real LAN access

- Put the Mac and the board on a phone hotspot (no client isolation) — needed if a phone must upload clips straight to the board.
- With `sudo`, add an NCM function to the USB gadget for a direct USB network link.

## Running NPU workloads once logged in

```sh
export LD_LIBRARY_PATH=~/git/executorch/build-x86/backends/qualcomm:/usr/lib
export ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"
```

`apt` on the board times out over IPv6; use `sudo apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 install ...`.
