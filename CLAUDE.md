# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hackathon project (Qualcomm IoT track, Arduino VENTUNO Q: Dragonwing IQ8 / QCS8275 + Hexagon NPU, with an STM32H5 MCU over Arduino Bridge): an on-device tennis serve coach. A phone films a serve, the board runs pose estimation on the NPU, and the app gives one correction at a time. Judging weights ExecuTorch integration (25/100) and on-device efficiency (15/100), so how a model runs on the board matters as much as whether it runs. The team doc is linked in `docs/context.md`; the board track guide is https://github.com/aaishikasb/qc-executorch-guide (IoT).

## Commands

Python 3.14 on macOS Apple Silicon; dependencies are pinned in `requirements.txt`.

```sh
sh setup.sh                                   # creates .venv and installs requirements

# 88-serve Djokovic reference analysis (offline; refuses an incomplete cohort unless --allow-partial)
.venv/bin/python reference/analyze.py --source reference/source --out reference/results --accept-provisional-h36m

# GIF renderer: reads ./visual_data.json, so run it from reference/
(cd reference && ../.venv/bin/python render_gif.py)

# six-serve smoke pipeline: fetch | analyze | run
.venv/bin/python smoke/pipeline.py run --layout h36m
```

Tests (run from repo root; each suite expects its own working directory):

```sh
(cd reference && ../.venv/bin/python -m unittest test_analysis -v)
(cd smoke && ../.venv/bin/python -m unittest discover -s tests -v)
node tests/test_visual_runtime.cjs
# single test:
(cd smoke && ../.venv/bin/python -m unittest tests.test_pipeline.PipelineTests.test_time_warp -v)
```

There is no linter or build step.

## Architecture

Three independent pieces, connected only by data files:

- **`reference/`**: pro-serve reference distribution. `analyze.py` reads the 88 Djokovic pose arrays `(T,17,3)` in `reference/source/` (UVA Tennis Serve Analysis Dataset, CC BY 4.0), derives eight 3D included joint angles, detects two heuristic events (deepest knee bend; highest right wrist), resamples each serve piecewise onto a 101-point grid (anchors at 0/40/80/100%), and writes stats to `reference/results/` (including a SHA-256 `manifest.json`). `render_gif.py` and the visualization use the `visual_data.json` snapshot, not `results/` directly.
- **`smoke/`**: the original six-serve end-to-end sample (fetch with checksum verification, angles, DTW alignment against one Djokovic serve). Superseded by `reference/` but kept as a tested example.
- **`visualization/`**: D3 page. `djokovic-88-serves.fragment.html` embeds its data inline in a `<script id="djoker-data">` block; `tests/test_visual_runtime.cjs` parses that block and runs the playback code against DOM/D3 test doubles (not a browser test). `tests/fixtures/original-playback.js` reproduces a former negative-array-index bug.
- **`demo/ventuno-pose/`** (in progress): first on-board pose pipeline. `posepipe.py` runs on the Mac and drives the board over `adb`: the Mac extracts frames (ffmpeg), letterboxes and computes the crop, then pushes raw float32 tensors; the board runs Qualcomm AI Hub MediaPipe Pose (detector 128x128, then landmarks 256x256) as QNN context binaries via `qnn-net-run` on HTP. The board path `/home/arduino/models/mp62` and DSP env vars are hard-coded. `render.py` draws the overlay, keyframe sheet and angle plots.

## Constraints that aren't obvious

- **The joint layout is provisional.** The dataset README says COCO, but the geometry matches MotionBERT's H36M order. Every entry point demands an explicit acknowledgement flag (`--accept-provisional-h36m` / `--layout h36m`). Keep that gate; don't silently assume a layout.
- **The reference poses are 3D, lifted from broadcast video; the board pipeline is 2D MediaPipe from a phone.** Their keypoint sets differ (H36M 17 vs MediaPipe's 25 upper-body landmarks; the current demo has no knees/ankles), so they can't be compared joint-for-joint without a mapping and a 2D projection.
- **The demo is not ExecuTorch yet.** `qnn-net-run` with AI Hub context binaries bypasses ExecuTorch. Scoring needs a `.pte` run by the ExecuTorch runtime with the QNN backend for QCS8275, or as a fallback XNNPACK on the CPU. The track's prepared bundle ships only `add.pte`, DINOv2 and Qwen3-0.6B; there is no pose model.
- **Phase events are heuristics on body landmarks, not ball contact or racket events.** The right-elbow minimum is recorded but deliberately not used for alignment (it hits the search boundary in 41/88 serves). No serve is silently excluded; quality issues are flagged in `phase_events.csv`.
- The existing code is not coaching advice. The planned coaching loop (one root fault at a time, external-focus cues, deterministic rules, LLM only for phrasing) and the offline amateur-clip benchmark are design decisions made by the team; check with the user before changing them.

## Style

The Python files use a dense style: imports and short statements joined with `;` on one line, minimal comments. Match the surrounding file. Results and docs state limitations explicitly (bands are between-serve percentiles, not confidence intervals; percentages are display coordinates). Keep that precision when adding results.
