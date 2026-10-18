# Djoker serve review (Next.js)

Local upload → RTMPose (Ventuno or Mac CPU) → timestamped playback and evidence-linked feedback.

## Run

From this directory:

```sh
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3017
```

Open http://127.0.0.1:3017. This is a local application. Direct phone access is not configured yet; upload a phone recording transferred to the Mac, or select an available local sample.

Requirements:

- Node.js 20.9+, npm, ffmpeg, ffprobe on PATH; adb for Ventuno.
- Python 3.10+ with NumPy and OpenCV. Set DJOKER_PYTHON to its absolute executable path. The existing demo/ventuno-pose/et/.venv-et/bin/python is reused when present; otherwise the default is the repository's .venv/bin/python. On a fresh checkout, create .venv at the repo root and install numpy and opencv-python-headless there.
- For Mac CPU: install onnxruntime in the configured Python environment. Set DJOKER_ONNX to the exported wholebody rtmpose_body2d.onnx (including its external data files). The default is demo/ventuno-pose/et/onnx/rtmpose_body2d.onnx. DJOKER_BACKEND=cpu forces CPU; otherwise an unavailable board falls back automatically. This model must output 133-joint SimCC tensors, not the separate body7 model.
- For Ventuno: connected board, serial 242692658 by default (DJOKER_SERIAL overrides).
- Existing board model: /home/arduino/models/et/rtmpose_qnn_fp16_QCS8275.pte.
- Existing board runner: /home/arduino/git/executorch/build-x86/examples/qualcomm/executor_runner/qnn_executor_runner and its QNN libraries. Model binaries and SDK installation are not part of this UI change.

## Workflow

1. Upload one serve (0.5–20 seconds, up to 128 MB).
2. Select the view and hitting hand. Drag a player box on the paused preview, including overhead hands and feet. The box is fixed throughout the clip; ensure the player remains inside it.
3. Process. Jobs are serialized locally and progress is shown in the interface.
4. Scrub, slow playback, toggle the skeleton, and click estimated Loading and Upward reach markers. Inspect the linked observation and download the result JSON from Processing & evidence.

Sample buttons appear only when their videos exist under benchmark/manual/samples/. They create fresh processing jobs; no precomputed feedback is substituted. Source files and uploaded media stay local.

## Architecture

- src/app/: Next.js App Router and responsive React interface; no Sites integration.
- src/app/api/: bounded streamed upload, job status, processing launch and ranged media delivery.
- processor/worker.py: preview normalization, job locking, device calls and result persistence.
- processor/pose.py: the existing wholebody model's BGR 0..255 NCHW input and SimCC output contract. This differs from the repository's separate normalized body7 ONNX model.
- processor/review.py: adapter to the existing dms, compare2d, and coaching modules. Uses strict mode; does not enable unvalidated reference comparisons.

The Mac decodes video, prepares crops, decodes results and runs coaching rules. The Ventuno executes the pose model through ExecuTorch QNN FP16 when connected. Otherwise ONNX Runtime runs the exported model on the Mac CPU. Each result records its actual backend and timings. The browser renders the video and skeleton. Full board-side orchestration is a later step.

Job folders are in local/web-jobs/ (or DJOKER_DATA_DIR). Each contains input, normalized playback, poster, status, log and result JSON; eligible clips also contain a DMS packet. Temporary frame/tensor files are removed after successful processing. Failed jobs retain diagnostics. No uploads are included in Git.

## Evidence limits

- Feedback currently provides descriptive measurements or a request for a clearer recording. Existing reference-based cues, drills and similarity scores stay blocked until validated.
- The event engine assumes a right-handed server; left/unknown handedness and unsupported views return a limitation while still displaying the tracked video.
- The browser shows estimated body events, not verified trophy position, ball toss, ball contact or landing. No ball/racket detector is present.
- The overlay's 0.3 score threshold is for display. Analysis applies separate joint visibility checks; scores are not calibrated probabilities.
- Preview normalization preserves playback duration at 30 fps; analysis samples that timeline at 20 fps. Slow-motion sources remain slow motion. Do not infer real movement speed from edited clips or claim native 60/120-fps event precision.
- Player selection is manual. Automatic identity tracking, multi-serve segmentation, webcam recording, direct phone networking and board-only processing are not implemented.
- The server and job files are for local use. An authenticated service is needed before exposing them beyond a trusted local environment.

## Checks

```sh
npm test
npm run build
# From repository root, using the configured Python:
demo/ventuno-pose/et/.venv-et/bin/python -m unittest discover -s web/processor -p 'test_*.py'
```

Tests cover upload rejection/decoding, seekable media, path validation, duplicate processing, crop contracts, overlay synchronization, QNN pre/postprocessing, strict feedback gates, event timing, retry after a device-transfer failure, and real CPU fallback inference (skipped if the local ONNX model is absent).
