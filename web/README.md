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

## Live Ventuno webcam

Choose **Manual recording** or **Automatic serve capture**, then use **Start camera** in the top panel at http://127.0.0.1:3017. The USB webcam must be connected to the Ventuno as `/dev/video0`; the board needs `ffmpeg`, and the Mac needs the local wholebody ONNX model and ONNX Runtime described above. No new board service or dependency installation is required.

**Manual recording (recommended for debugging):** click **Start recording**, perform one serve, then click **Stop & analyse**. Low joint scores and tracking loss do not stop or discard the recording. At 19 seconds it saves automatically. Recordings use a 30-fps timeline and retain a `tracking.json` beside the job's video with joint coordinates/scores, visibility flags and the automatic detector's state per observation. The saved clip runs through the same review worker. Stopping the camera mid-recording preserves an interrupted clip for later review instead of deleting it.

For automatic capture, keep one right-handed player fully in the frame, from the side or rear. The current automatic mode uses the full frame; move the camera to exclude other people and include overhead hands and feet. RTMPose is a top-down pose estimator, so presence is inferred from sustained confident body joints, not a separate person/identity detector.

- Half a second of visible body tracking starts recording, including up to 0.75 seconds of buffered lead-in.
- The hitting wrist must be visibly overhead in consecutive observations (at least 0.06 seconds), then below the shoulder for 0.8 seconds to finish the clip. This is an **experimental motion-completion heuristic**, not verified serve or ball-contact detection. Other overhead gestures can trigger it.
- Tracking loss for one second or 18 seconds without completion discards the attempt. A transport gap over 0.5 seconds resets the attempt. A two-second cooldown allows another serve without leaving frame.
- Completed recordings become normal review jobs automatically. The page opens their existing skeleton playback, loading/reach markers and strict feedback. Capture pauses during analysis; wait for the next ready state before serving again.
- **Stop camera** stops the camera; an unfinished automatic attempt is discarded, while a manual recording is preserved. If a completed clip is processing, it finishes that step before releasing the camera. Closing the browser does not stop an explicitly started session; use the Stop button.

Architecture: the board's `ffmpeg` streams 640×480 video over ADB; the Mac runs continuous ONNX pose tracking and records at 15 fps with timestamp resampling. The existing processor runs saved-clip pose inference on the Ventuno NPU (or its existing CPU fallback). The camera sends compressed JPEG frames at 30 fps; a continuous multipart JPEG preview avoids replacing the image URL on each refresh. Actual preview rate depends on tracking and transport throughput. JPEG framing recovers from fragmented reads or diagnostic bytes without shifting colour channels. No audio is recorded. This is not fully board-side live inference.

Runtime files live in `local/web-jobs/live/`, separate from UUID review jobs. `status.json`, `worker.log`, and `camera.log` provide diagnostics. The process lease prevents duplicate camera owners across app reloads. No recordings/models are committed.

Validation: camera preview and start/stop were checked on the connected Brio 101. A prerecorded Sara clip passed through the recording adapter and Ventuno review worker. Automatic start-to-finish capture of a person serving still needs a physical camera test; these checks do not establish segmentation accuracy.

## Workflow

1. Upload one serve (0.5–20 seconds, up to 128 MB).
2. Select the view and hitting hand. Drag a player box on the paused preview, including overhead hands and feet. The box is fixed throughout the clip; ensure the player remains inside it.
3. Process. Jobs are serialized locally and progress is shown in the interface.
4. Scrub, toggle the skeleton, and select a body-movement stage. Each available stage replays its evidence interval at 0.25× and stops at the interval end. **Analyse with Gemma** reviews the available stage evidence and selects a replay focus without requiring a pro overlay. Download the result JSON from Processing & evidence.

## Movement stages and Gemma review

`processor/stages.py` adds six experimental body-movement categories: setup, tossing-arm rise, loading, upward swing/reach, follow-through, and finish/recovery. Each has an estimated interval and representative frame, or an explicit unavailable reason. Stages can overlap. An arm rise is not ball release; highest wrist is not contact; a settled recovery is not proof of landing. Cocking/racket drop remains unavailable without supporting racket evidence. The eight-stage context is linked in the UI.

The existing `events` loading/reach contract remains compatible with the professional overlay. The overlay still aligns on those two anchors; new user-stage intervals are not independently validated reference alignment points. Pose analysis still samples at 20 fps. This feature does not claim higher capture precision or infer real speed from slow-motion footage.

The main review shows a measured observation and replay cue for each available stage. `POST /api/commentary` with only `{jobId}` loads the stored result on the server and sends the supported observations to **Gemma 3 1B on Ventuno through ExecuTorch QNN**. Gemma selects one evidence ID; the returned observation and cue are drawn from that evidence, not free-form diagnosis. It sees measurements, not video. The older loading-comparison commentary endpoint is retained. Unavailable, busy, or rejected model output has a visibly labelled measured fallback, never a fabricated Gemma result. Cache keys include stage evidence and prompt version; rejected/unavailable replies can be retried.

Validation includes missing tossing-arm evidence, short tracking interruptions, walk-in timestamp offsets, clipped finish, supported model selections, rejection of invented evidence, offline fallback, API job validation and bounded stage replay. Saved clips are development examples, not a held-out accuracy benchmark. In the latest live recording, setup, tossing-arm rise, loading and upward swing are supported; follow-through and finish remain unavailable because arm tracking is incomplete.

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
- Player selection is manual. Automatic identity tracking, validated multi-serve segmentation, direct phone networking and board-only processing are not implemented. Experimental live capture is described above.
- The server and job files are for local use. An authenticated service is needed before exposing them beyond a trusted local environment.

## Checks

```sh
npm test
npm run build
# From repository root, using the configured Python:
demo/ventuno-pose/et/.venv-et/bin/python -m unittest discover -s web/processor -p 'test_*.py'
```

Tests cover upload rejection/decoding, seekable media, path validation, duplicate processing, crop contracts, overlay synchronization, QNN pre/postprocessing, strict feedback gates, event timing, retry after a device-transfer failure, and real CPU fallback inference (skipped if the local ONNX model is absent).

## Professional serve comparison

Completed reviews offer an individual Djokovic or Sinner serve to overlay on the uploaded video. The reference endpoint reads the committed 101-frame aligned pose arrays and phase metadata; it does not require pandas, another model, or a video download. Choose the player, first/second serve and an individual recording.

When the upload has ordered loading and reach events, playback maps them to reference phase 40 and 80 respectively. This changes reference playback speed between phases; it is not a comparison of real-time motion speed. Missing events disable the overlay. Reference pose reconstruction and projected knee measurements run behind the scenes; the UI shows the aligned overlay on the uploaded video and the practice focus, without a separate skeleton preview or angle table. The camera stays fixed behind the reference; no angle adjustment is exposed.

Both cohorts contain individual poses, not original broadcast videos. Attribution and recorded quality flags are visible under Reference source & limitations. Reference selection defaults to a serve with stable event estimates, not an ideal technique or an averaged body.

## Overlay replay and on-board commentary

Click **Overlay Djokovic/Sinner · 0.25×** after selecting a reference. Playback starts just before loading at quarter speed. The green user skeleton and dashed blue reference share the video canvas. The reference is first rotated once into an estimated rear view using its post-reach hip axis (phases 85–100). The overlay stays at that rear view without rotation or mirroring; torso size and position are then matched to the user. Individual limbs are not warped to match. Missing phase/torso evidence disables overlay; loss of hip tracking temporarily hides it. Hide overlay restores normal speed.

A loading-position comparison selects one provisional knee-bend practice focus. It is an exploratory reference comparison, not a validated technique diagnosis or instruction to match exact pro angles. The `/api/commentary` route sends the measured angles and approved cue to the existing Gemma 3 1B ExecuTorch/QNN runner on Ventuno. The model may rephrase the cue; a validator rejects new measurements, unsupported body/action advice, and reversed bend directions. Board errors, busy status or rejected replies retain explicit template provenance. Validated responses are cached by evidence; requests and runner output are stored under `local/commentary/` (ignored). Each board request uses its own directory under `/home/arduino/djoker-commentary/`, a 60-second runner timeout, and the existing model/tokenizer pair. No model binaries or SDKs are checked into Git.

Model paths are in `processor/commentary.py`. This uses Gemma rather than Qwen because the supplied IoT guide does not publish its Qwen model/tokenizer bundle. Model loading and generation happen on the board; pose alignment and deterministic measurements happen on the Mac. This is not a vision-language model watching the video, nor unconstrained LLM diagnosis.

Live recordings now derive a fixed horizontal player crop from at least ten full-body tracking observations, with padding and the full image height retained for raised hands and feet. Explicit player crops are preserved. Review quality checks exclude leading/trailing frames without full-body visibility; missing joints within the retained interval still face the same confidence and coverage gates. Event timestamps and frame indices remain relative to the original, untrimmed video.

## Rear-view reference subset

The comparison picker now exposes only pose sequences with a stable post-reach horizontal hip direction (mean unit-vector coherence ≥0.90). This retains 60/88 Djokovic and 181/219 Sinner serves. Every retained sequence receives one rigid rotation into an estimated rear view; distances, joint identity and motion are preserved. The entire serve uses the same rotation. The camera is fixed at the rear orientation, with no angle slider or automatic yaw fitting. It does not mirror to force a fit. Only uploads marked rear view can enable this overlay.

These are **derived rear projections**, not verified original rear-camera recordings. The source metadata has no camera-view label and the available pose coordinates are not a validated camera calibration. The method assumes the player faces the court after upward reach. Original arrays and full-cohort statistics remain intact. Excluded sequences cannot be selected through the API.

`reference/results/rear_view_manifest.json` and `sinner/results/rear_view_manifest.json` record every inclusion/exclusion, orientation coherence, rotation, source hash and limitations. Rebuild with `demo/ventuno-pose/et/.venv-et/bin/python reference/audit_rear_views.py`. The API applies the same policy at read time.

Automatic capture uses a full-height portrait crop that follows the visible player and falls back to the full frame after one second without a confirmed body. After a confirmed overhead motion, stopping requires at least 0.5 seconds of observed lowered-arm evidence over a minimum 0.8-second follow-through interval. Unknown gaps of up to 0.25 seconds pause evidence collection; longer gaps reset it. Completion requires a currently visible body and lowered wrist. An observation gap over 0.5 seconds resets motion evidence. The rear-serve regression fixture preserves only timestamps and boolean signals; the latest 5.6-second test recording completes at 5.53 seconds in replay. This is replay verification, not validation across players or proof of live end-to-end behaviour.
