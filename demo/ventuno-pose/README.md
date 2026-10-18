# Ventuno pose demo (first pass)

Clip: "Althea Gibson - Tennis Champion" (USIA film, public domain, Wikimedia Commons), 52-62 s at 12 fps.
Pose: Qualcomm AI Hub MediaPipe Pose v0.62.0 (QAIRT 2.45 context binaries) run on the Ventuno Q NPU via `qnn-net-run`.
Mac does frame extraction, crop/ROI math and drawing; the board runs both models (detector 128x128, landmarks 256x256).

- `overlay.mp4` skeleton overlay (6 fps playback = half speed; git-ignored, rebuilt by `render.py`)
- `sheet.png` 16 keyframes (3.3 MB, git-ignored, not produced by a committed script), `angles.png` elbow angles / wrist height
- `et/` ExecuTorch QNN/XNNPACK exports and board proof (`et/README.md`); `proof/` latency / agreement results
- `keypoints.json` per-frame ROI + 25 landmarks (x, y px, z, vis)
- `posepipe.py`, `render.py` pipeline and renderer (need numpy, opencv, matplotlib; board path/env hard-coded to /home/arduino/models/mp62)

Known limits: 25 landmarks only (no knees/ankles); detector also fires on non-players (ball boy, crowd); 2D only.
