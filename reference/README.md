# Djokovic: 88-serve reference distribution

Computed 17 October 2026 from the published Tennis Serve Analysis Dataset. All 88 Novak Djokovic poses were read, checked for shape and finite values, and matched to metadata filenames and frame counts. There are 7,329 frames (60–91 per serve), 75 first serves, 13 second serves, and three matches: Albot (34), Djere (23), Popyrin (31). No serves were silently excluded.

## Animation and data

- `djokovic-88-serves.gif`: animated mean normalized skeleton and eight joint-angle trajectories. Solid curves are arithmetic means; shaded bands are the pointwise 10th–90th percentiles across serves. Playback is slowed and phase-normalized; it is not original video timing.
- `raw_joint_angles.csv`: all 7,329 frames × eight derived angles, plus filename/frame keys.
- `phase_events.csv`: per-serve estimated landmarks, smoothing sensitivity, and quality flags.
- `aligned_trajectories.npz`: full arrays, including angles on estimated-phase and original-progress grids, normalized aligned poses, and filenames.
- `distribution.json`: means, sample standard deviations, quantiles, individual phase-aligned angle curves, and group results.
- `manifest.json`: Drive file IDs and SHA-256 checksums for all 88 poses.
- `summary.json`: concise numerical findings.

Each serve has equal weight. Bands are between-serve distributions, **not confidence intervals**. The 88 serves are observations from one player in three matches, not independent population samples. The all-serve mean is dominated by first serves (75 of 88). Use the first/second serve selector in the interactive visualization for separate distributions; n=13 second serves is a small group.

## What the results show

At the estimated deepest-knee-bend event:

| Included angle | Mean | 10th–90th percentile |
|---|---:|---:|
| Left knee | 102.4° | 95.0–107.9° |
| Right knee | 117.7° | 104.1–125.6° |

An included angle of 180° means a straight joint; these numbers are not flexion angles measured from zero. Deepest knee bend occurs at a median 54.5% of the original clip, with a 10th–90th percentile span of 52.7–59.1%. The highest-right-wrist estimate occurs at median 81.2%, with a much wider 65.5–84.8% span. Do not treat these clip percentages as times measured from toss release.

Upper-arm trajectories show substantially more scatter than the hip trajectories. This distribution combines actual motion differences, alignment uncertainty, and pose-estimation artifacts; it is not a set of ideal coaching targets.

## Angle definitions and joint mapping

The export is interpreted as H36M, **provisionally**. The dataset README calls it COCO, but observed joint-0 geometry and visually coherent H36M skeletons support the MotionBERT interpretation. Dataset-author confirmation is still needed. Coordinate axes and any handedness transforms are unverified. We use inferred z-up geometry only for the wrist-height proxy and pose display.

All angles use the 3D included angle between vectors A−B and C−B, in degrees:

| Angle | A / B / C indices |
|---|---|
| Left elbow | 11 / 12 / 13 |
| Right elbow | 14 / 15 / 16 |
| Left shoulder | 12 / 11 / 4 |
| Right shoulder | 15 / 14 / 1 |
| Left hip | 11 / 4 / 5 |
| Right hip | 14 / 1 / 2 |
| Left knee | 4 / 5 / 6 |
| Right knee | 1 / 2 / 3 |

Shoulder and hip measurements are simple segment angles, not standardized anatomical rotations. They do not measure shoulder external rotation, pronation, or racket orientation. The downloaded source angles were unavailable; these are our derived definitions.

## Estimated phases and alignment

1. **Loading:** clip start → deepest knee bend. Locate the minimum mean left/right knee included angle within 15–70% of the clip after a five-frame moving average. The search window is a heuristic to avoid selecting landing flexion.
2. **Drive & upward swing:** deepest knee bend → highest right wrist. Locate the maximum smoothed right-wrist z coordinate after the loading event and before 95% of the clip.
3. **Follow-through:** highest right wrist → clip end.

Every serve is linearly resampled within these segments onto a shared 101-point grid: start=0%, knee event=40%, wrist event=80%, end=100%. These percentages are display coordinates chosen for comparison, not biomechanical phase durations. No arbitrary individual serve is used as the reference template. No DTW is applied in this population analysis.

The right-elbow minimum between the knee and wrist events is retained as a diagnostic in `phase_events.csv`, but **is not used as an alignment boundary**: it hits the search interval boundary in 41 of 88 serves. We therefore do not claim a validated cocking/racket-drop phase. Ball release, racket low point, maximum shoulder external rotation, contact, and landing cannot be reliably identified from these inputs alone.

Only phase detection uses a moving average. The displayed angle trajectories are computed from the unsmoothed poses and then linearly resampled; averaging across serves does not remove all source noise. The interactive original-progress mode offers a second view without event alignment.

## Quality and uncertainty

- All 88 serves contain at least one adjacent-frame jump greater than 40° in one of the eight derived angles. This is a diagnostic threshold, not a validated failure classifier.
- 27 serves have at least one internal event (including the unused elbow event) shift by more than max(4 frames, 5% of clip length) when the smoothing window changes among 3, 5, 7, and 9 frames.
- Three wrist maxima hit the allowed search boundary; one has a broad maximum plateau.
- These flags are recorded, not used to silently discard serves. Their inclusion widens the descriptive distribution.
- No confidence-score channels or source video were available for this analysis. Phase labels need manual video validation before coaching use.

## Mean-pose animation

For display, each serve is scaled by its median root-to-upper-torso length (joints 0–8), rotated once around z to align its initial hip axis, and centered horizontally on the pelvis. Vertical movement is retained relative to its initial pelvis height. The animated skeleton is the pointwise coordinate mean of these aligned poses. Averaging can shorten apparent limbs; this is a statistical display, not a physically reconstructed ideal serve.

Angles are averaged independently from each individual pose. Because angles are nonlinear, the displayed mean skeleton's geometric angle need not equal the plotted mean angle. In the interactive view, joint ellipses show marginal 10th–90th percentile spans after projection; they are not joint 80% probability regions. The animation carries no ground, racket, or ball model.

## Reproduce offline

The companion `djokovic-reference.zip` contains all 88 source arrays, full metadata, source IDs, analysis code, dependencies, tests, results, and the animation.

From the unpacked folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python analyze.py --source source --out results --accept-provisional-h36m
```

Analysis needs no network once dependencies are installed. Python 3.14/macOS Apple Silicon was used. The explicit H36M flag acknowledges the unresolved export-layout conflict. The default analysis refuses to generate a population result if any of the 88 poses are missing. `--allow-partial` is for development only and marks completeness false.

Validation: all 88 source checksums verified; per-serve array/frame checks passed; tests confirmed event ordering, exact preservation of alignment anchors, all-serve averaging, and standard-deviation/quantile calculation. Three tests passed. The GIF was rendered and inspected. Interactive JavaScript passed syntax checking; browser preview was unavailable under the current app policy.

## Sources and attribution

Jason Wang et al., *Large-Scale 3D Pose Estimation of Professional Tennis Serves from Broadcast Video*, University of Virginia, 2026. Dataset licensed CC BY 4.0; see `DATA_LICENSE`. Our modifications are derived angles, estimated phase landmarks, normalization, statistics and visualization.

- Dataset repository: https://github.com/jasnwag/tennis_serve_dataset (inspected commit 7889457cc9b50b0c2a9fdcc81d786bcdb6b8652c)
- Published data: https://drive.google.com/drive/folders/1Wr7UjMvgLwgqCQ09wSaw94ozvRYRO8fB
- H36M layout evidence: https://github.com/Walter0807/MotionBERT/blob/main/lib/utils/vismo.py
- Serve-phase context: https://pmc.ncbi.nlm.nih.gov/articles/PMC3445225/ — published stages rely on events that these body-only arrays do not directly observe. Our phase estimates are not that paper's validated detector.
