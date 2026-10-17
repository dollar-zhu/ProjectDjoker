# Project Djoker

Working six-serve dataset smoke pipeline for a two-day tennis coaching hackathon.
Built and run on 2026-10-17. No GPU, trained model, API key, or video download needed.

## Run

Tested on macOS Apple Silicon with Python 3.14. Dependencies are pinned to the tested environment in `requirements.txt`; other Python/platform combinations have not been tested.

```sh
cd "$HOME/Projects/Project Djoker"
sh setup.sh
.venv/bin/python pipeline.py run --layout h36m
.venv/bin/python -m unittest discover -s tests -v
```

`run` downloads missing sample files, verifies every SHA-256, validates metadata/arrays, computes four joint-angle trajectories, aligns each sample to one Djokovic first serve using DTW, and saves reports. Existing matching files are reused. `analyze --layout h36m` runs fully offline. `fetch --data PATH` fetches the pinned sample into another directory. Changed or corrupt input fails clearly rather than silently changing results. A fresh download needs public Google Drive access; quotas or sharing changes can block it.

## Actual results

- Full metadata: 5,966 rows × 20 columns, 109 servers, 113 matches; filenames unique.
- Djokovic: 88 rows, 75 first serves / 13 second serves. Albot match: 34; Djere: 23; Popyrin: 31.
- Six downloaded poses: three Djokovic, one Sinner, two Rakhimova; includes first and second serves and both metadata gender categories. This is a purposive smoke sample, not a statistically representative cohort.
- Pose arrays: float32, `(T,17,3)`, T = 77–89; every coordinate finite, frame counts match metadata.
- Four available upstream velocity arrays: float32 `(T,8)`, all finite. They are validated but not used for coaching or derivatives because units are unverified.
- Downloaded payload: 223,809 bytes (metadata + six poses + four velocities), excluding indexes/repository/environment.
- Example diagnostic: two Djokovic first serves (`1164_pt0004` vs `1164_pt0008`) yield a right-elbow mean absolute angle gap of 5.77° along an 85-pair DTW path. This is a model-space comparison under a provisional joint mapping, not a technique score.

## Outputs

- `reports/results.json`: full observed schema, null counts, sample shapes, angle ranges, comparisons.
- `reports/djokovic_metadata.csv`: all 88 Djokovic rows.
- `reports/*_angles.csv`: computed left/right elbow and knee angles in degrees.
- `reports/*_dtw_path.npy`: reference/sample frame index pairs.
- `reports/angle_trajectories.png`: raw trajectories on normalized sequence progress.
- `reports/pose_check.png`: three frames of the reference pose for visual inspection.

## Schema and documentation mismatches

Actual metadata columns:

```
filename match_id server returner gender height_cm point_number point_winner
serve_number speed_kmh serve_width serve_depth return_depth n_frames
duration_sec quality_label ace rally_count set_no game_no
```

Join using `filename`, not row index. Do not use README names `server_gender`, `Speed_KMH`, or `ServeNumber`; do not run the older CSV examples against this Parquet release. Null counts: serve_width 173, serve_depth 173, return_depth 638, quality_label 6. Outcome code meanings are not verified; this pipeline does not interpret quality_label as a coaching label.

The README says fixed-length aligned sequences; the actual six pose files have differing lengths and match `n_frames`. We therefore perform our own diagnostic alignment and do not assume prealignment. DTW is endpoint constrained with average absolute angle distance, equal joint weighting, and no phase labels or warping window. It can over-align motion and should not be used as a quality score.

### Joint mapping is provisional

The dataset docs call the 3D layout COCO. Observed joint 0 has exactly zero x/y throughout the reference sequence, and limbs/head form a coherent H36M skeleton; coordinates also extend outside the claimed [0,1] range. This agrees with MotionBERT's documented H36M output convention. We infer H36M for this demonstration, but the author has not confirmed the export mapping or axis transformations. The CLI requires `--layout h36m` to make acceptance explicit. No automatic COCO fallback.

Used triplets (shoulder/elbow/wrist or hip/knee/ankle): left elbow 11/12/13, right elbow 14/15/16, left knee 4/5/6, right knee 1/2/3. Physical coordinate units, handedness transforms, and source video FPS remain unverified. No physical velocity, contact frame, trophy position, racket drop, injury claim, or prescriptive coaching is inferred.

## Data availability blockers

Both the connected Drive listing and public folder listing returned zero files for `joint_angles` and `angular_accelerations`. The public listings returned 5,500 keypoint entries and 2,696 velocity entries, short of 5,966 metadata rows; these are observed listing counts, not proof of permanent deletion or complete inventories. All six chosen keypoints and four matching velocities were found. Two selected velocities were absent from the retrieved listing. Snapshots are saved in `*_listing.json`. Missing source angles are worked around by computing four angles from the poses.

This repository ships documentation/assets, not an executable video-to-pose extraction implementation. User video ingestion, consistent pose extraction, handedness normalization, phase detection and coaching validation remain outside this completed dataset smoke pipeline.

## Two-day next steps

Day 1: confirm export joint order/units; manually check a reference serve against source video; make the six-sample comparison browsable. Then add one user clip using a deliberately consistent pose representation. Do not directly compare MediaPipe's 33 landmarks with these 17 joints.

Day 2: test upload-to-report on a small set of clips; add manually checked phase alignment and one evidence-backed coaching cue only after the geometry is validated. Keep speed prediction and complex learned scoring out of the demo.

## Provenance and attribution

Dataset: Jason Wang et al., *Large-Scale 3D Pose Estimation of Professional Tennis Serves from Broadcast Video*, University of Virginia, 2026. CC BY 4.0; copied license in `DATA_LICENSE`. Our changes are sample selection, validation, derived angles and diagnostic comparisons.

- Source: https://github.com/jasnwag/tennis_serve_dataset
- Pinned repository commit: `7889457cc9b50b0c2a9fdcc81d786bcdb6b8652c`; local checkout in `upstream/`.
- Published Drive: https://drive.google.com/drive/folders/1Wr7UjMvgLwgqCQ09wSaw94ozvRYRO8fB
- Sample source file IDs, byte counts and SHA-256: `manifest.json`.
- MotionBERT joint mapping evidence: https://github.com/Walter0807/MotionBERT/blob/main/lib/utils/vismo.py (17-joint H36M mapping). This supports our inference, not confirmation of this dataset's export.
