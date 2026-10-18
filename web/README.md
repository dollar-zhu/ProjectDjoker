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

Choose **Continuous · every serve** (the default), **Ready gesture · automatic capture** or **Manual recording**, then use **Start camera** in the top panel at http://127.0.0.1:3017. The USB webcam must be connected to the Ventuno as `/dev/video0`; the board needs `ffmpeg`, and the Mac needs the local wholebody ONNX model and ONNX Runtime described above. No new board service or dependency installation is required.

**Manual recording (recommended for debugging):** click **Start recording**, perform one serve, then click **Stop & analyse**. Low joint scores and tracking loss do not stop or discard the recording. At 19 seconds it saves automatically. Recordings use a 30-fps timeline and retain a `tracking.json` beside the job's video with joint coordinates/scores, visibility flags and the automatic detector's state per observation. The saved clip runs through the same review worker. Stopping the camera mid-recording preserves an interrupted clip for later review instead of deleting it.

**Continuous capture** removes the ready gesture and countdown, so you can serve repeatedly without returning to the camera:

- Stand still with your whole body visible and both arms below overhead for one second; low-confidence dropouts under 0.3 seconds pause rather than restart this. **Getting set** then becomes **Watching**. Walking in, holding a raised arm, or the tail of the previous serve cannot arm detection.
- While watching, the same `MotionFinish` reach → descent → recovery detector used by ready-gesture mode marks a serve. The Mac keeps a rolling 4-second buffer, so each clip starts 3.5 seconds before the first overhead observation (setup, tossing-arm rise and loading) and ends at the observed recovery. A clip never reaches back before the settled stance, so an earlier uncaptured movement cannot become its reach. If the hitting wrist reaches the top image edge during the serve, the capture is flagged with a framing warning, because review cannot locate the reach frame.
- An overhead arm held for 2 seconds, 4 seconds from reach without a recovery, 1 second of body loss, or a 0.5-second transport gap discards the attempt. After a capture or discard, a 1.5-second cooldown applies, then the player must settle again.
- Reviews are prepared on a background thread while the camera keeps tracking. The page stays on the camera and lists **Serve 1, 2, …** for this session with review status; it does not navigate away. **Stop camera** releases the camera first, then finishes any captured serves still being reviewed.
- Each frame's detector inputs and state are written to `live/continuous.jsonl` to explain missed or unexpected captures.
- This is **not a serve classifier**: any overhead arm movement that finishes like a serve (a wave or stretch that is released quickly) can be captured, and review applies its usual evidence gates. The detector replays the committed live fixtures (`live-serve-168`, `serve-setup-2b7`) to start → complete. The trimmed clip of `live-serve-168` reproduces all six movement stages at the same times as the full clip. Back-to-back physical serves and false triggers on court have not yet been tested on the board camera.

For ready-gesture capture, keep one right-handed player fully in the frame, from the side or rear. Tracking starts with the full frame, then follows the player with a full-height portrait crop; move the camera to exclude other people and include overhead hands and feet. RTMPose is a top-down pose estimator, so presence is inferred from confident body joints, not a separate person/identity detector.

- Raise either hand near shoulder height, with the elbow below the wrist, and hold for 0.75 seconds. The whole body must remain visible. Walking or a brief arm swing alone does not arm recording.
- A large **3 → 2 → 1** countdown appears. Lower your hand and prepare, then serve on **GO**. Recording and its tracking trace begin at GO; the ready gesture and countdown are excluded. A 0.5-second tracking loss or transport gap cancels the countdown. Brief loss cannot start a recording while the person is unseen.
- After an observed overhead reach, recording follows the downward arm movement into recovery. A visible lowered wrist can establish descent; when the wrist is hidden, a dropping elbow plus visible torso recovery can establish it instead. Short unknown intervals pause evidence, and whole-body loss cannot complete a serve. Complete stillness is not required. This is an **experimental body-motion completion detector**, not verified serve or ball-contact detection. Other overhead movements performed after GO can satisfy it.
- Tracking loss for one second or 18 seconds without completion discards the attempt. A transport gap over 0.5 seconds resets the attempt. After completion or cancellation, visibly lower the ready hand before raising it again; the same held cue cannot continually retrigger attempts. There is a two-second cooldown after completed/discarded attempts.
- Completed recordings become normal review jobs automatically. The page opens their existing skeleton playback, loading/reach markers and strict feedback. Capture pauses during analysis; wait for the next ready state before serving again.
- **Stop camera** stops the camera; an unfinished automatic attempt is discarded, while a manual recording is preserved. If a completed clip is processing, it finishes that step before releasing the camera. Closing the browser does not stop an explicitly started session; use the Stop button.

Architecture: the board's `ffmpeg` streams 640×480 video over ADB; the Mac runs continuous ONNX pose tracking and records at 15 fps with timestamp resampling. The existing processor runs saved-clip pose inference on the Ventuno NPU (or its existing CPU fallback). The camera sends compressed JPEG frames at 30 fps; a continuous multipart JPEG preview avoids replacing the image URL on each refresh. Actual preview rate depends on tracking and transport throughput. JPEG framing recovers from fragmented reads or diagnostic bytes without shifting colour channels. No audio is recorded. This is not fully board-side live inference.

Runtime files live in `local/web-jobs/live/`, separate from UUID review jobs. `status.json`, `worker.log`, and `camera.log` provide diagnostics. The process lease prevents duplicate camera owners across app reloads. No recordings/models are committed.

Validation: ready-pose and countdown tests cover transient gestures, partial visibility, observation gaps, cancellation and repeat attempts. A deterministic camera integration test verifies countdown status, first recorded frame at GO and completed review submission. Fresh pose-model replay of four saved serve videos found no accidental ready triggers (incidental holds lasted 0.167–0.4 seconds); those videos do not contain an intentional ready hold, so a new positive physical-camera test is still needed. Pose replay now also tests wrist-occluded finishes using observed elbow/body recovery, alongside held-overhead, single-spike, walking and body-loss cases. This small development set does not establish detection accuracy.

## Workflow

1. Upload one serve (0.5–20 seconds, up to 128 MB).
2. Select the view and hitting hand. Drag a player box on the paused preview, including overhead hands and feet. The box is fixed throughout the clip; ensure the player remains inside it.
3. Process. Jobs are serialized locally and progress is shown in the interface.
4. Scrub, toggle the skeleton, and select a body-movement stage. Each available stage replays its evidence interval at 0.25× and stops at the interval end. **Get coaching with Gemma 4** produces one supported practice focus, a plain-language cue, a short drill and a check for the next recording, without requiring a pro overlay. Download the result JSON from Processing & evidence.

## Movement stages and Gemma review

`processor/stages.py` adds six experimental body-movement categories: setup, tossing-arm rise, loading, upward swing/reach, follow-through, and finish/recovery. Each has an estimated interval and representative frame, or an explicit unavailable reason. Stages can overlap. An arm rise is not ball release; highest wrist is not contact; a settled recovery is not proof of landing. Cocking/racket drop remains unavailable without supporting racket evidence. The eight-stage context is linked in the UI.

The existing `events` loading/reach contract remains compatible with the professional overlay. Motion alignment keeps those two anchors and adjusts timing within phases; setup/finish evidence bounds the compared interval. These are estimated body phases, not independently validated reference alignment points. Pose analysis still samples at 20 fps. This feature does not claim higher capture precision or infer real speed from slow-motion footage.

The main review puts practice instructions ahead of measurements. Raw stage measurements remain in collapsed tracking details and result JSON. `POST /api/commentary` accepts only `{jobId}`, loads the stored result, and derives supported candidates without sending raw angles or video to the language model. **Gemma 4 E2B runs on Ventuno CPU through Ollama**, reached by ADB executing loopback HTTP on the board. There is no Mac/cloud/Gemma 3 fallback. This is not verified NPU acceleration or autonomous visual diagnosis.

When framing/track evidence is insufficient, the app asks for a usable recording immediately without invoking Gemma or claiming the model failed.

The shared coach v3 prompt lives in `coaching/board_feedback.py` (`coach_request`). The app selects the first supported practice card in rhythm, recovery, preparation order. Gemma receives only that approved cue and returns a short `speech` response, checked by the shared coach validator. `processor/coaching_cards.json` retains the authored observation, purpose, drill and success check. The earlier local focus-selection prompt is stashed for later iteration. Missing tracking never becomes a fault, and similarity to a professional never prescribes an ideal knee angle. A conservative repeated-frame gate asks for a clearer recording when more than 90% of consecutive reduced frames are almost identical; it also may reject extreme repeated-frame slow motion. It does not detect every edited or poor recording.

Unavailable, busy or rejected model output retains a visibly labelled practice-card fallback. Cache keys include video, supported evidence, quality gate, prompt, card content, model digest and generation settings. Only completed accepted generations are cached. Raw requests, responses and timings are kept under ignored `local/commentary/`. A valid response is not proof of coaching accuracy; the development evaluation and manual-review gaps are documented in `docs/research/2026-10-18-gemma4-ventuno-feedback.md`.

Validation includes missing tossing-arm evidence, short tracking interruptions, walk-in timestamp offsets, clipped finish, supported model selections, rejection of invented evidence, offline fallback, API job validation and bounded stage replay. Saved clips are development examples, not a held-out accuracy benchmark. The latest saved recording now supports follow-through and finish through observed elbow/body recovery even while the hitting wrist is occluded. Stage metadata is versioned as `body-stages-v2`.

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

- Coaching feedback provides descriptive measurements or a request for a clearer recording. The older Djokovic coaching rating remains blocked until validated. The separate selected-serve body-similarity score below is explicitly experimental and is not technique quality.
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

When the upload has ordered loading and reach events, playback anchors them to reference phase 40 and 80 respectively. `src/lib/motion-similarity.ts` then uses constrained dynamic time warping within each phase to follow different execution speeds. It excludes walk-in/out and does not extrapolate through an unobserved finish. Missing anchors disable alignment; an uncertain finish can still allow an explicitly partial replay. The camera stays fixed behind the reference; no angle adjustment is exposed.

The separate **Experimental body similarity** score compares twelve torso/limb joints against the selected individual serve. User and reference share hip centering and one fixed torso scale fitted at loading, with no mirroring, yaw search or individual limb stretching. The score and overlay use the same time mapping and spatial fit. Alignment is monotonic, anchored at loading/reach, bounded to a 20% band within each phase and a maximum 2:1 local timing stretch. Execution speed is not independently penalized.

Motion completion is separate from measurement coverage. Once setup, reach and recovery are supported, similarity uses only the observed joint samples. Region weights keep hitting arm (35%), tossing arm (25%), legs (30%) and torso (10%) represented; a hidden wrist can leave the observed elbow supporting that arm. A whole missing dynamic region during a phase still prevents a misleading score. Low-confidence samples are excluded rather than invented or treated as mismatches. The UI shows weighted joint coverage, per-region coverage and the excluded measurements; a numeric score with partial tracking is distinct from an unavailable motion. Long observation gaps and absent phases still limit alignment. The 0–100 conversion uses a provisional exponential scale of normalized pose distance, `100·exp(−d/1.75)`, chosen so typical amateur distances (0.4–0.7) read about 65–80 rather than 30–50; it is not a calibrated accuracy percentage, biomechanical assessment or ranking of serve quality. Perspective and estimated reference poses remain limitations.

Both cohorts contain individual poses, not original broadcast videos. Attribution and recorded quality flags are visible under Reference source & limitations. Reference selection defaults to a serve with stable event estimates, not an ideal technique or an averaged body.

## Overlay replay and on-board commentary

Click **Overlay Djokovic/Sinner · 0.25×** after selecting a reference. Playback starts at the supported alignment's beginning and stops at its end, at quarter speed. The green user skeleton and dashed blue reference share the video canvas. The reference is first rotated once into an estimated rear view using its post-reach hip axis (phases 85–100). The overlay stays at that rear view without rotation or mirroring; torso size and position are then matched to the user. Individual limbs are not warped to match. Missing phase/torso evidence disables overlay; loss of hip tracking temporarily hides it. Hide overlay restores normal speed.

The legacy loading-position endpoint now describes the comparison without prescribing a deeper or shallower bend. It returns reviewed template provenance; it does not call Gemma 3. Use the main coaching panel for the Gemma 4 practice plan.

### Gemma 4 on Ventuno

The current installation uses the official ARM64 Ollama runtime under `/home/arduino/djoker-gemma4/runtime`, with `gemma4:e2b` model files under `/home/arduino/djoker-gemma4/models`. The service binds to **127.0.0.1 on the board**, with cloud features disabled. No new LAN port or Mac HTTP forwarding is needed. The runtime and model weights are not committed.

Install or refresh the persistent user service from the repository root:

```sh
web/processor/start_gemma4_ventuno.sh
adb -s 242692658 shell 'curl -fsS http://127.0.0.1:11434/api/tags'
.venv/bin/python web/processor/eval_coach.py --out local/gemma4-eval
```

The start script expects the installed runtime and E2B model. On a new board, install the [official ARM64 runtime](https://docs.ollama.com/linux#arm64-install) into that runtime directory, set `OLLAMA_MODELS` to the models directory, and pull `gemma4:e2b` on the board. The evaluation fixture references this workspace's local recordings/results; it fails when those assets are missing rather than inventing results. Replace paths with available reviewed fixtures for a fresh checkout. Model inference is forced to CPU with four threads and a 4096-token context. `DJOKER_SERIAL` selects the ADB board; `DJOKER_GEMMA_MODEL` accepts only `gemma4:e2b` in this evaluated path.

The script enables `djoker-gemma4.service` in the board's user systemd manager, with restart on failure. User lingering is already enabled for `arduino` on this board; it is required for startup without login. Logs are available with `journalctl --user -u djoker-gemma4.service` (ADB shells need `XDG_RUNTIME_DIR=/run/user/1000` and `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`). Reboot startup is configured but has not been tested by rebooting the board.

The API allows up to 140 seconds for the board process; board inference itself is bounded at 120 seconds. A second concurrent request gets a labelled busy fallback. The model receives the selected approved cue, not raw measurements or video frames. The Mac still performs framing checks, evidence preparation, validation and rendering; pose inference retains its separate existing NPU/CPU path.

Live recordings now derive a fixed horizontal player crop from at least ten full-body tracking observations, with padding and the full image height retained for raised hands and feet. Explicit player crops are preserved. Review quality checks exclude leading/trailing frames without full-body visibility; missing joints within the retained interval still face the same confidence and coverage gates. Event timestamps and frame indices remain relative to the original, untrimmed video.

## Rear-view reference subset

The comparison picker now exposes only pose sequences with a stable post-reach horizontal hip direction (mean unit-vector coherence ≥0.90). This retains 60/88 Djokovic and 181/219 Sinner serves. Every retained sequence receives one rigid rotation into an estimated rear view; distances, joint identity and motion are preserved. The entire serve uses the same rotation. The camera is fixed at the rear orientation, with no angle slider or automatic yaw fitting. It does not mirror to force a fit. Only uploads marked rear view can enable this overlay.

These are **derived rear projections**, not verified original rear-camera recordings. The source metadata has no camera-view label and the available pose coordinates are not a validated camera calibration. The method assumes the player faces the court after upward reach. Original arrays and full-cohort statistics remain intact. Excluded sequences cannot be selected through the API.

`reference/results/rear_view_manifest.json` and `sinner/results/rear_view_manifest.json` record every inclusion/exclusion, orientation coherence, rotation, source hash and limitations. Rebuild with `demo/ventuno-pose/et/.venv-et/bin/python reference/audit_rear_views.py`. The API applies the same policy at read time.

Automatic capture uses a full-height portrait crop that follows the visible player and falls back to the full frame after one second without a confirmed body. `MotionFinish` in `processor/capture.py` tracks observed reach, descent and recovery across short wrist occlusions; both live recording and the movement-stage extractor use it. The comparison's cached-result fallback uses matching temporal rules. The evidence records measured wrist/elbow descent, body recovery displacement and observed duration. Missing coordinates are never reconstructed as measurements. Saved-video pose fixtures and deterministic live-loop tests verify this sequence, but a newly recorded ready gesture and physical-camera attempt remain necessary to establish live behavior.
