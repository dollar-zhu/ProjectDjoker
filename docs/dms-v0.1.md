# Project Djoker DMS v0.1

Interchange contract for reference and live serve pipelines. This implementation makes the proposed joint/feature orders explicit; both teams must adopt these versioned definitions. Shape equality does not establish scientific comparability.

## Packet

Each shot occupies its own directory with one JSON file and four NumPy arrays:

| Payload | Shape | Missing values |
|---|---|---|
| Pose | `(T,17,2)` or `(T,17,3)` | NaN coordinates |
| Angles | `(T,8)` | NaN |
| Joint confidence | `(T,17)` | NaN if unavailable |
| Timestamps, seconds from start | `(T,)` | All NaN if unavailable |

Arrays must be floating-point, not object/pickle arrays. Infinity is invalid. JSON uses `null` for unavailable numbers and events. All tensor paths are local `.npy` basenames. Arrays must share T. Observed timestamps start at zero and strictly increase; variable frame intervals are supported, so fps may be null even with observed timestamps. Do not derive an unverified fps from clip length.

[JSON Schema](dms-0.1.schema.json) describes metadata. The Python validator also checks the actual tensors, timestamps, event ranges, and calculated angle values; JSON Schema alone cannot validate those.

## canonical17 joint order

This version chooses the COCO anatomical ordering as an interchange convention, independent of the source model:

```
0 nose              1 left_eye          2 right_eye
3 left_ear          4 right_ear         5 left_shoulder
6 right_shoulder    7 left_elbow        8 right_elbow
9 left_wrist       10 right_wrist      11 left_hip
12 right_hip       13 left_knee        14 right_knee
15 left_ankle      16 right_ankle
```

`mapping_validated: true` asserts a documented anatomical mapping, not accurate tracking in every frame. Include `mapping_evidence`. A packet is never labeled canonical17 when mapping is unvalidated. Do not assign H36M head landmarks to eyes/ears by guessing.

## dms-angles-v1 column order

| Column | Name | Canonical indices A/B/C |
|---:|---|---|
| 0 | left_elbow_flexion | 5 / 7 / 9 |
| 1 | right_elbow_flexion | 6 / 8 / 10 |
| 2 | left_knee_flexion | 11 / 13 / 15 |
| 3 | right_knee_flexion | 12 / 14 / 16 |
| 4 | left_shoulder_angle | 7 / 5 / 11 |
| 5 | right_shoulder_angle | 8 / 6 / 12 |
| 6 | left_hip_angle | 5 / 11 / 13 |
| 7 | right_hip_angle | 6 / 12 / 14 |

Every value is the interior angle at B:

`degrees(arccos(clip(dot(A-B,C-B)/(norm(A-B)*norm(C-B)),-1,1)))`

Despite the `_flexion` names in the proposal, a straight elbow/knee is **180°**, not 0°. Shoulder/hip values are segment angles, not clinical rotations. Missing joints and zero-length segments yield NaN. The validator checks every finite, validated feature against the supplied pose within 0.001°.

The existing analysis order is elbows, shoulders, hips, knees. Conversion to DMS order uses `[0,1,6,7,2,3,4,5]`; old result files are unchanged. Tests establish equivalence with our own local calculations only, not with unpublished author calculations.

## Coordinate and confidence semantics

`source` includes model, coordinate_system, camera_view, fps, axis_convention, units, and metric_space. For 2D image angles, coordinates must use an isotropic image metric: multiply normalized x by image width and y by image height. Raw normalized coordinates on a non-square image distort angles.

`features.representation` is `projected_2d` or `estimated_3d`. MediaPipe image-space z is never promoted into metric 3D. Its separately provided world landmarks would require a separately validated adapter and camera/coordinate compatibility review.

`joint_confidence.kind` distinguishes:

- `tracking_score`: model-provided per-joint score, with `score_definition` identifying its meaning.
- `availability`: binary present/missing indicators, **not** tracking quality.
- `unavailable`: an all-NaN tensor.

Scores from different definitions are not treated as equivalent. The comparison defaults to a 0.5 tracking and event threshold, configurable in the Python API. These are integration thresholds, not calibrated accuracy probabilities or validated coaching cutoffs.

A shared, nonempty `source.comparison_profile_id` is required for comparisons. It denotes a camera/coordinate compatibility profile that the teams have actually checked. Do not copy a profile ID between incompatible captures merely to pass validation. A broad label such as `rear_oblique` alone does not prove comparable projection.

## Events

Each event is null or an object with `frame`, `timestamp`, `confidence`, `method`, `definition_id`, and `status` (`estimated` or `validated`). An event needs a frame or an observed timestamp. If both are provided they must agree. Unknown confidence stays null; detector confidence is not invented from a heuristic.

Only matching `definition_id` values identify the same event semantics. `max_knee_flexion` can mean the minimum included knee angle, but teams must agree on which knee or bilateral statistic, search window, smoothing, and validation before assigning the same ID. Contact is null unless supported by an actual detector or annotation.

The first comparison implementation compares the two selected knee angles at one validated event. It does not compare entire trajectories by matching raw frame numbers or perform automatic resampling/mirroring. Timestamp-only events must exactly identify an observed sample; interpolation is not silently applied.

## Fail-closed comparison

`compare_event` checks packet validity, feature definitions/units, validated anatomical mapping, representation, coordinate and camera compatibility, handedness, event semantics/validation/confidence, finite selected features, and confidence for the joints used by those metrics.

A failed essential check returns `comparable: false`, one primary `reason`, and additional `reasons` when available. No distance, score, or coaching is produced. Compatible packets return left/right measurements and their signed difference in degrees, not a technique score. A successful gate relies on honest provenance and metadata; it does not prove biomechanical validity.

## Current Djokovic export

Run from repository root:

```sh
.venv/bin/python -m dms export-reference --out dms-reference
.venv/bin/python -m dms validate dms-reference/2024-usopen-1164_pt0004_srv1/2024-usopen-1164_pt0004_srv1.json
```

The exporter verifies all 88 input hashes before exporting. Output must be a new/empty directory.

- Poses retain original indices with `joint_schema: djoker17_unvalidated`, `joint_names: null`, and `mapping_validated: false`. No canonical reordering is performed.
- Angles are recomputed under the existing provisional hypothesis and reordered into the DMS feature order; `definitions_validated: false`.
- Source coordinate system/units, camera view, handedness, fps and comparison profile remain unknown/unverified where the dataset does not establish them.
- Timestamps and tracking scores are all NaN; fps is null. Finite pose coordinates are not used to invent confidence.
- Knee/wrist events remain estimated, with confidence and timestamp null. Contact and racket drop are null.

These packets validate structurally and **must fail comparison** until essential evidence is available. This is an honest transport format for provisional data, not a conversion to canonical geometry.

## Live pipeline integration

`dms.adapters.export_mediapipe_image` accepts already captured `(T,33,2|3)` normalized image landmarks, `(width,height)`, observed timestamps, and `(T,33)` visibility or None. It maps documented anatomical indices, converts XY to pixels, discards image Z, computes eight angles, and writes a packet. It does not run MediaPipe or record video.

```python
from dms.adapters import export_mediapipe_image

packet_path = export_mediapipe_image(
    output_directory,
    landmarks=landmarks,           # Actual model output, T x 33 x 2 or 3
    image_size=(width, height),    # Coordinate frame used by that output
    timestamps=timestamps,        # Actual capture times, rebased to zero
    visibility=visibility,        # Actual per-joint scores, or None
    shot_id=shot_id,
    player=player,
    handedness=handedness,
    camera_view=camera_view,
    comparison_profile_id=None,    # Set only after compatibility is checked
    events={"max_knee_flexion": None, "contact": None},
)
```

Anatomical left/right refers to the player's body. Handle display mirroring, crop transforms, letterboxing, pixel aspect, and image dimensions consistently before export. The adapter assumes the documented MediaPipe layout and does not correct a caller's mislabeled input.

For an already validated canonical tensor, use `dms.export_canonical`. Mapping evidence, observed timestamps, confidence semantics, and events are explicit arguments. Your colleague's code has not been modified or run here; they need to call one of these adapters and supply a real packet for integration validation.

MediaPipe index and coordinate reference: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
