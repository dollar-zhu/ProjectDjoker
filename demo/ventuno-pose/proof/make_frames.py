"""Build 20 RTMPose crops (1x3x256x192 float32, 0..255 BGR, same convention as posepipe.rtm_input) from
nvidia_serve_overlay.mp4 using the MediaPipe detector on the board for the ROI (last ROI reused when the detector
misses). Writes proof/frames/fNN.raw + MNN.npy (crop->frame affine) + pngs, and et/calib/*.npy for int8 calibration."""
import cv2, numpy as np, sys, os
sys.path.insert(0, "."); import posepipe as P
cap = cv2.VideoCapture("nvidia_serve_overlay.mp4"); frames = []
while True:
    ok, f = cap.read()
    if not ok: break
    frames.append(f)
sel = list(range(4, len(frames), 5))[:20]
rgb = [cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB) for i in sel]
lb = [P.letterbox(r, 128) for r in rgb]
det = P.run_batch("pose_detector", [(x[0].astype(np.float32) / 255)[None] for x in lb], "et/eval_work", "det")
os.makedirs("proof/frames", exist_ok=True); os.makedirs("et/calib", exist_ok=True); roi = None
for k, (i, res, (_, s, l, t), r) in enumerate(zip(sel, det, lb, rgb)):
    ds = P.decode_detections(res, 0.3); roi = P.roi_from_detection(ds[0], s, l, t) if ds else roi
    crop, M = P.rtm_crop(r, roi); x = P.rtm_input(crop)
    x.astype("<f4").tofile(f"proof/frames/f{k:02d}.raw"); np.save(f"et/calib/f{k:02d}.npy", x); np.save(f"proof/frames/M{k:02d}.npy", M); cv2.imwrite(f"proof/frames/f{k:02d}.png", cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)); cv2.imwrite(f"proof/frames/src{k:02d}.png", frames[i])
print("wrote", k + 1, "crops from frames", sel)
