# Project Djoker

Tennis serve reference analysis for a two-day coaching hackathon. Includes a reproducible six-serve smoke pipeline and an analysis of all **88 Novak Djokovic serves** in the published Tennis Serve Analysis Dataset.

## Verified results

- Dataset metadata: 5,966 serves, 109 players, 113 matches.
- Djokovic cohort: 88 serves, 75 first serves and 13 second serves, across three matches; 7,329 frames.
- Eight derived joint-angle trajectories with means, sample standard deviations, and pointwise 10th–90th percentile bands.
- Estimated loading, drive/upward-swing, and follow-through phases.
- Animated mean pose and angle plots, plus interactive group selection and playback.

![Reference analysis](reference/preview.png)

## Setup and run

Tested with Python 3.14 on macOS Apple Silicon. Dependencies are pinned.

```sh
sh setup.sh
.venv/bin/python reference/analyze.py \
  --source reference/source \
  --out reference/results \
  --accept-provisional-h36m
```

All 88 source pose arrays and metadata are included, so analysis works offline after dependency installation. `--download` retrieves missing files from the public source; without `--allow-partial`, analysis refuses an incomplete cohort.

For the original six-serve smoke test:

```sh
.venv/bin/python smoke/pipeline.py run --layout h36m
```

## DMS interchange contract

The [DMS v0.1 specification](docs/dms-v0.1.md) defines canonical17, eight explicit angle definitions, timestamps, confidence semantics, and fail-closed event comparisons. It includes a MediaPipe image-output adapter and a provisional Djokovic exporter. Neither adapter invents missing timestamps, confidence, or mapping validation.

```sh
.venv/bin/python -m dms export-reference --out dms-reference
.venv/bin/python -m unittest discover -s tests -p "test_dms.py" -v
```

Djokovic packets are structurally valid but are rejected for comparison until anatomical mapping and essential compatibility conditions are validated.

## Video → 2D skeleton (RTMPose)

`pose2d/` runs RTMPose-m (body7, 256×192, ONNX from OpenMMLab) on a video with a fixed operator crop: no person detector. Preprocessing follows the model's own `pipeline.json` (1.25 padding, aspect-fixed affine, **BGR→RGB**, ImageNet mean/std, SimCC split 2.0). The model is downloaded once to `models/` and checked against pinned SHA-256 hashes.

```sh
.venv/bin/pip install -r requirements-pose.txt
.venv/bin/python -m pose2d.video path/to/serve.mov --crop x1,y1,x2,y2 --out runs/dev/<shot> \
  --shot-id <shot> --handedness right --camera-view <label>
.venv/bin/python -m unittest tests.test_pose2d -v
```

Each run writes `dms/` (a validated DMS packet: canonical17 pixel xy, `projected_2d` angles, observed timestamps in seconds), `rtmpose_native.npz` (unclipped raw output and crop), `run.json` (video/model hashes, preprocessing, provider, timings, score summary), `contact_sheet.jpg` and `overlay.mp4`. Choose the crop so the player stays inside it for the whole motion and other people stay out.

Scores are raw SimCC peak responses (mean of x/y), which can exceed 1. The DMS copy clips them to [0,1]; they are not calibrated probabilities. Joints are still emitted when occluded, with lower scores, so downstream gates must use confidence. This is a development-host run, not board inference.

## 2D comparison against Djokovic (knee loading)

The board runs only 2D pose, so the 3D reference is brought to 2D offline. `compare2d.reference` rotates each Djokovic serve into level orthographic cameras from −90° to +90° around the profile view. 0° looks along the hip line at the deepest knee bend, i.e. a camera behind the server. It then runs the **same** 2D event detector the live path uses and stores both knee angles at the deepest bend, per view angle. `compare2d.compare` estimates the live camera's view angle from apparent hip width, picks the matching reference slice, and applies the gates.

```sh
.venv/bin/python -m compare2d.reference            # writes reference/projected2d/
.venv/bin/python -m compare2d.compare runs/dev/<shot>/dms/<shot>.json --out runs/dev/<shot>/compare [--serve-type 1|2]
.venv/bin/python -m unittest tests.test_compare2d -v
```

- **Source chirality:** the source poses are mirror images. The export matches mmpose's demo transform, which is a reflection: nose and knee directions disagree with the hip-implied facing in 86/88 serves. x is negated before projecting. Interior angles are unaffected.
- **Events:** loading = minimum smoothed mean knee angle before the highest right wrist. If the knees keep bending after that wrist peak, the serve is excluded rather than guessed (6 of 88 Djokovic serves). At the profile view, the 2D loading frame matches the 3D estimate within ±2 frames in 82/82 remaining serves.
- **View:** the ±30° band keeps the projected knee angle near its 3D value. Square-on views (≈90°) read almost straight legs and are rejected. On reference data, the hip-width view estimate is within about ±7° at 15–45°. Live COCO hip landmarks add unmeasured error.
- **Outputs:** `comparison.json` is the production result. It stays `insufficient_evidence` with null deltas until validation records exist: provisional joint mapping, unvalidated events and camera profile, and unknown serve type. `diagnostic.json` and `knee_vs_djokovic.png` hold the unvalidated measurements.

## Board feedback decision and Qwen phrasing

`coaching/board_feedback.py` is what the device runs after a serve. It reads a DMS packet, `reference/projected2d/board_reference.json` (50 KB lookup table) and `coaching/rules.json`, and needs only numpy. It selects at most one cue, plus optional praise, deterministically by priority. By default the Djokovic-relative rules are blocked because no validation records exist, and it falls back to a descriptive observation. `--allow-unvalidated-reference` enables them for demos, and the output is labelled as such.

```sh
.venv/bin/python -m coaching.board_feedback decide runs/dev/serve1/dms/serve1.json --out runs/dev/serve1/board_demo --allow-unvalidated-reference
# Any OpenAI-compatible Qwen server (Ollama shown); set "model" in qwen_request.json to your Qwen tag
curl -s http://localhost:11434/v1/chat/completions -H 'Content-Type: application/json' -d @runs/dev/serve1/board_demo/qwen_request.json \
  | .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])' \
  | .venv/bin/python -m coaching.board_feedback validate runs/dev/serve1/board_demo/feedback.json -
```

Qwen only rephrases. `validate` accepts its speech only if it is ≤25 words, uses only the player's own measured numbers, introduces no body part or action outside the approved text, and avoids injury, speed, racket and guarantee claims. Otherwise it returns the canonical text. Rule thresholds are draft values awaiting review.

## Djokovic match score

Every serve that passes the reference gates gets a 0–100 **Djokovic match score** (`coaching/rating.json`, `coaching/rating.py`). Eleven measurements are scored. Each gets 100 inside Djokovic's typical band at the matched camera view and falls linearly to 0 at a set distance outside it. The total is a weighted mean, itemized in `feedback.json`, with a score range for ±10° of camera-angle error.

| Group | Metrics (weight) | Band |
|---|---|---|
| Legs, 65% | front knee (17), back knee (17) at the deepest bend; bend timing (10); push-up timing (6); leg-drive speed (10); drive-to-contact timing (5) | 10th–90th percentile |
| Trophy, 15% | hitting-elbow lift (upper arm vs trunk) at the deepest bend (10); toss-hand height (5) | 25th–75th / 10th–90th |
| Arm–leg timing, 8% | how early the hitting elbow folds before the deepest bend | 25th–75th |
| Contact, 12% | elbow extension (7); hand height (5) at the highest-wrist contact proxy | 10th–90th |

**Not measured, and why:**
- **Racket-drop depth:** trophy and drop folds look alike in 2D from behind, and the reference is unstable in that phase.
- **Pronation:** it finishes within ~10 ms, the body skeleton has no hand orientation, and the reference has no hand or racket data.
- **Racket path and ball:** no racket or ball tracking.

Each serve speaks one cue, selected by priority. Other matching findings (e.g. trophy elbow, arm timing) are recorded as `secondary_findings`.

The score measures similarity to one reference player, **not** quality: the PRD lists quality scores as out of scope, so its wording needs updating if this ships. It is withheld on retries, when under 60% of the weight was measured, and whenever Djokovic-relative feedback is blocked (including strict mode). Weights and thresholds are draft values.

## Board package

`pip install .` provides `djoker-run`, `djoker-check` and `djoker-feedback`, with runtime dependencies numpy, OpenCV (headless) and onnxruntime only. `pip install '.[tts]'` adds Piper speech. `scripts/build_bundle.py` builds an offline board tarball containing the model, reference table, rules, config and scripts. Readiness, the module map and porting steps are in [docs/board-port.md](docs/board-port.md). `djoker-check` compares the device against private golden fixtures from one of your own clips (`scripts/make_golden.py --video clip.mov --crop x1,y1,x2,y2` → `local/golden/`, git-ignored). They are never committed because they contain a real player.

## Run the coach: webcam or saved video

Both sources go through the same path: `live/camera.py` (frame source), `live/pose.py` (RTMPose, no detector), `live/session.py` (6 s pose buffer, trigger, DMS packet, rule engine, optional Qwen), and `live/audio.py`.

```sh
# Saved video: one serve per clip; analyzes the last 4 s once at the end (warns if the clip is longer)
.venv/bin/python scripts/run_live.py --source path/to/serve.mov --allow-unvalidated-reference   # config/dev.json

# Webcam (laptop camera = webcam, USB/UVC phone on the board = webcam:/dev/video0): press Enter right after each serve
.venv/bin/python scripts/run_live.py --source webcam --audio say --allow-unvalidated-reference
```

- **One serve per analysis:** a saved clip should contain one serve; it is analyzed once at the end. Longer clips print a warning and analyze only the last `analysis.window_s` seconds. On the webcam, trigger once after each serve. There is no automatic serve detection; for an existing multi-serve video, pass `--trigger-at` with the end time of each serve.
- **Crop:** without `--crop`, the next crop comes from the previous frame's confident keypoints, falling back to the full frame when tracking is lost. On Serve1 it locked onto the server from the second frame and produced the same decision as the hand-set crop. Use `--crop x1,y1,x2,y2` for a fixed setup.
- **Optional flags:** `--qwen-url http://localhost:11434/v1/chat/completions --qwen-model <tag>` adds Qwen rephrasing (1 s timeout, then canonical text). `--audio wav` plays `audio/<SPEECH_CODE>.wav` when present.
- **Voice:** `--audio piper` speaks offline with [Piper](https://github.com/OHF-Voice/piper1-gpl) neural TTS. It runs on the onnxruntime we already ship. The default voice `en_US-joe-medium` (63 MB, CC0 voice data) synthesizes a 5 s sentence in about 60 ms on the dev host; the voice loads once at startup (~0.6 s). Download it once with `.venv/bin/python -c "from live.audio import fetch_voice; fetch_voice()"` (checked against a pinned SHA-256). Choose another voice with `--voice <file>.onnx` or `audio.voice`. If the package, voice or player is missing, it falls back to `say`/`espeak-ng`, then text. piper-tts is GPL-3.0-or-later, so it is an optional extra (`djoker[tts]`).
- **Outputs:** each shot writes `runs/<session>/<shot>/` (DMS packet, raw RTMPose output, `feedback.json`, `speech.json`). Each session writes `timings.jsonl` and `health.jsonl`. Raw video is never recorded. Saved-video sessions are labelled `replay`.
- **Board:** the Enter key stands in for the physical completion button (`Session.trigger`).

## View the animation

Open `visualization/index.html` in a browser. The interactive charts require the pinned D3 library from jsDelivr. The source fragment is `visualization/djokovic-88-serves.fragment.html`.

The self-contained [animated GIF](reference/djokovic-88-serves.gif) works without JavaScript or internet access. Read [methods and limitations](reference/README.md) for interpretation.

## Tests

From the repository root:

```sh
(cd reference && ../.venv/bin/python -m unittest test_analysis -v)
(cd smoke && ../.venv/bin/python -m unittest discover -s tests -v)
node tests/test_visual_runtime.cjs
```

The visualization regression harness reproduces the former negative-array-index error and checks frame timing, pause/replay, scrubbing, group/alignment changes, and restored state. It uses lightweight DOM/D3 test doubles; it is not a browser rendering test.

## Layout

- `reference/source/`: 88 source pose arrays, full metadata, and Drive IDs.
- `reference/results/`: raw and aligned trajectories, phase estimates, distribution statistics, and SHA-256 manifest.
- `reference/analyze.py`: cohort analysis.
- `reference/render_gif.py`: animation renderer using the included `visual_data.json` snapshot.
- `smoke/`: original six-serve end-to-end sample.
- `visualization/`: corrected interactive visualization and standalone preview.
- `tests/`: playback regression checks.

## Known limitations

The dataset documentation identifies COCO joints, while observed geometry suggests MotionBERT's H36M ordering. **H36M remains provisional** and requires explicit acknowledgement when running analysis. Body poses do not provide ball or racket tracking. Phase boundaries are heuristic body-landmark estimates, not confirmed contact or racket-drop events.

All 88 serves have at least one abrupt derived-angle jump. Variation includes tracking noise and phase-alignment uncertainty. No serves are silently excluded. The mean pose is a statistical display; its geometric angles need not equal the independently averaged joint angles. This project does not yet accept user video or generate validated coaching advice.

## Source and attribution

Dataset: Jason Wang et al., *Large-Scale 3D Pose Estimation of Professional Tennis Serves from Broadcast Video*, University of Virginia, 2026.

- Repository: https://github.com/jasnwag/tennis_serve_dataset
- Inspected commit: `7889457cc9b50b0c2a9fdcc81d786bcdb6b8652c`
- Dataset release: https://drive.google.com/drive/folders/1Wr7UjMvgLwgqCQ09wSaw94ozvRYRO8fB
- Dataset license: CC BY 4.0, reproduced in [DATA_LICENSE](DATA_LICENSE).

This project adds sample selection, derived angles, estimated phases, normalization, statistical summaries and visualizations. The dataset license applies to the source data; no separate license is assigned here to newly authored project code.
