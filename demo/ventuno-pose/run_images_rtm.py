import sys, os, math
import numpy as np, cv2
sys.path.insert(0, "."); import posepipe as P
paths = sys.argv[1:]; os.makedirs("imgs_out", exist_ok=True)
ims = [cv2.imread(p) for p in paths]; rgb = [cv2.cvtColor(i, cv2.COLOR_BGR2RGB) for i in ims]
lb = [P.letterbox(r, 128) for r in rgb]
det = P.run_batch("pose_detector", [(x[0].astype(np.float32) / 255)[None] for x in lb], "eval_work", "rtmdet")
rois = []
for k, (res, (_, s, l, t)) in enumerate(zip(det, lb)):
    ds = P.decode_detections(res, 0.3); rois.append(P.roi_from_detection(ds[0], s, l, t) if ds else None)
idx = [k for k, r in enumerate(rois) if r]
crops = [P.rtm_crop(rgb[k], rois[k]) for k in idx]
rt = P.run_batch(P.RTM_BIN, [P.rtm_input(c[0]) for c in crops], "eval_work", "rtm")
for j, k in enumerate(idx):
    xy, sc = P.rtm_decode(rt[j], crops[j][1]); im = ims[k].copy(); th = max(2, im.shape[1] // 300)
    for a, b in P.COCO_BONES:
        col = (60, 60, 255) if (a % 2 == 0 and a > 0) or (b % 2 == 0) else (255, 160, 40)
        cv2.line(im, tuple(map(int, xy[a, :2])), tuple(map(int, xy[b, :2])), col, th * 2, cv2.LINE_AA)
    for q in range(17):
        c = (0, 255, 0) if sc[q] > 4 else (0, 165, 255)
        cv2.circle(im, tuple(map(int, xy[q, :2])), th * 2, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.putText(im, "RTMPose on NPU", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 3, cv2.LINE_AA)
    out = f"imgs_out/{os.path.splitext(os.path.basename(paths[k]))[0]}_rtm.png"; cv2.imwrite(out, im)
    print("wrote", out, "| joint conf", dict(zip(P.COCO17, np.round(sc, 1))))
