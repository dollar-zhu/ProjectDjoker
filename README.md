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
