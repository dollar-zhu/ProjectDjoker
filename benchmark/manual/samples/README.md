# Local input samples

Extracted 17 October 2026. Original camera framing and source playback speed retained; audio removed. These are local reference/development excerpts, not licensed training data or independent evaluation cases. Exact URLs, time ranges, hashes and metadata are in [manifest.json](manifest.json).

| Input | Original source time | Use |
|---|---|---|
| Federer | 00:10–00:20 | Positive loading-to-extension reference; landing absent |
| Bremen | 00:13.8–00:16.3 | Toss review; side view needed for depth |
| Sara | 02:20.5–02:23.3 | Foot placement and late-step review |
| Stephen | 04:54–04:57 | Front/oblique view; reject rear-view scoring |
| Vishal | 03:00–03:04 | Small split-screen player; request original recording |

The Reddit amateur clip is **pending**: direct extraction failed and the available browser presented a CAPTCHA. No other video was substituted for it. Its URL is preserved in the manifest.

## Ventuno result

The existing ExecuTorch QNN FP16 RTMPose model ran successfully on the connected Ventuno for **230/230 sampled frames** across Federer, Bremen and Sara. Every result had the expected two SimCC tensors (133×384 and 133×512) with finite values. Body overlays use the first 17 COCO joints.

- Mean reported model inference: **4.46 ms/crop**; p95 **4.73 ms**.
- Process peak RSS: **49.88 MiB**.
- Sampling: **15 fps of source playback**, including source slow motion.
- Manual fixed player crops. Automatic person detection and identity tracking were not tested.
- Mac: video decoding, preprocessing, output decoding and drawing. Ventuno: model execution. This is not end-to-end live-camera throughput.

Run reports, logs, keypoints and overlays remain in the ignored local `runs/` directory.



Visual review of selected setup, loading, swing and recovery frames shows the skeleton on the intended players, with useful gross torso and leg motion. Occluded arms and fast wrists still need closer review. No labeled keypoints were supplied, so this is an execution/visual sanity check, not an accuracy score. Joint-score threshold 0.3 is a display setting, not a calibrated probability. Body joints alone do not identify the ball, racket, court line or shoe-ground contact needed for some coaching claims.

The runner logged a QNN-version warning and ignored output-pointer override errors, then completed successfully and produced all expected output tensors. These messages remain in the log rather than being hidden.

To repeat, from the repository root:

```sh
demo/ventuno-pose/et/.venv-et/bin/python benchmark/manual/extract_samples.py
demo/ventuno-pose/et/.venv-et/bin/python benchmark/manual/run_ventuno_samples.py --serial 242692658
```

Extraction expects the existing local source files in `../cache/`. Each inference run creates a unique local and board directory. Clips, raw tensors, and run artifacts stay local and are ignored by Git; scripts and manifests are reviewable source files.
