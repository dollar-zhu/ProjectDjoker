"""Explicit audio checks (no automatic pairing, downloads, or default sink changes).

python -m live.audio_check doctor --address AA:BB:CC:DD:EE:FF
python -m live.audio_check pair --address AA:BB:CC:DD:EE:FF
python -m live.audio_check trust --address AA:BB:CC:DD:EE:FF
python -m live.audio_check connect --address AA:BB:CC:DD:EE:FF
python -m live.audio_check play --address AA:BB:CC:DD:EE:FF --wav audio/READY.wav
python -m live.audio_check greeting --address AA:BB:CC:DD:EE:FF --voice models/piper/voice.onnx
python -m live.audio_check synthesize --voice models/piper/voice.onnx --text hello --output hello.wav
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

from .audio import Speaker
from .bluetooth import BluetoothRoute, GreetingController, GreetingGate


def parser():
    root = argparse.ArgumentParser(description='Inspect or explicitly use a selected Bluetooth audio device.')
    commands = root.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Read-only command availability and selected device state')
    doctor.add_argument('--address', required=True)
    doctor.add_argument('--timeout', type=float, default=5)
    for action in ('pair', 'trust', 'connect'):
        cmd = commands.add_parser(action, help=f'Explicitly {action} the selected device')
        cmd.add_argument('--address', required=True)
        cmd.add_argument('--timeout', type=float, default=30)
    for action in ('play', 'greeting'):
        cmd = commands.add_parser(action)
        cmd.add_argument('--address', required=True)
        cmd.add_argument('--timeout', type=float, default=15, help='Subprocess timeout in seconds')
        cmd.add_argument('--backend', choices=('piper', 'wav', 'espeak', 'say'), default='piper')
        cmd.add_argument('--voice', help='Local Piper .onnx model; never downloaded automatically')
        cmd.add_argument('--wav-dir', default='audio')
        if action == 'play':
            source = cmd.add_mutually_exclusive_group(required=True)
            source.add_argument('--wav', type=Path, help='Existing WAV to play on the selected route')
            source.add_argument('--text', help='Text to synthesize then play')
        else:
            cmd.add_argument('--debounce', type=float, default=1.0)
            cmd.add_argument('--interval', type=float, default=0.25)
            cmd.add_argument('--duration', type=float, default=10.0, help='Bounded observation window')
    synth = commands.add_parser('synthesize', help='Write native Piper WAV, without playback or Bluetooth operations')
    synth.add_argument('--voice', required=True)
    synth.add_argument('--text', required=True)
    synth.add_argument('--output', type=Path, required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'synthesize':
            with Speaker('piper', voice=args.voice) as speaker:
                speaker.synthesize(args.text, args.output)
            print(json.dumps({'ok': True, 'output': str(args.output)}))
            return 0
        route = BluetoothRoute(args.address, timeout=args.timeout)
        if args.command == 'doctor':
            report = route.doctor()
            print(json.dumps(report))
            return 0 if report['selected']['audio_ready'] else 1
        if args.command in ('pair', 'trust', 'connect'):
            print(json.dumps({'ok': True, 'output': route.action(args.command)}))
            return 0
        backend = 'wav' if args.command == 'play' and args.wav else args.backend
        wav_dir = args.wav.parent if args.command == 'play' and args.wav else args.wav_dir
        if args.command == 'play' and args.wav and not args.wav.is_file():
            raise FileNotFoundError(args.wav)
        if args.command == 'play' and args.wav and args.wav.suffix != '.wav':
            raise ValueError('--wav must name a .wav file')
        with Speaker(backend, wav_dir, args.voice, route=route, timeout=args.timeout) as speaker:
            if args.command == 'play':
                result = speaker.speak(args.text or '', args.wav.stem if args.wav else None)
                print(json.dumps(asdict(result)))
                return 0 if result.ok else 1
            if args.interval <= 0 or args.duration <= 0:
                raise ValueError('interval and duration must be positive')
            controller = GreetingController(speaker, GreetingGate(args.debounce))
            deadline = time.monotonic() + args.duration
            greeted = False
            while time.monotonic() < deadline:
                state = route.status()
                result = controller.update(state['audio_ready'])
                print(json.dumps({'selected': state, 'heart': controller.heart,
                                  'greeting': asdict(result) if result else None}), flush=True)
                if result is not None:
                    if not result.ok: return 1
                    greeted = True
                time.sleep(args.interval)
            return 0 if greeted else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
