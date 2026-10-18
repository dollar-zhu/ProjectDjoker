"""Keypoint agreement of the on-board ExecuTorch runs (outputs pulled by bench_board.py) against full-precision
onnxruntime on the Mac, for the 20 crops in ../proof/frames: SimCC argmax -> crop px (/2), mean pixel error,
PCK@0.05 (threshold = 0.05 * 256 = 12.8 px of the crop height; keypoints with ORT conf < 0.3 excluded), on the 17
COCO body joints. Writes ../proof/agreement.json and an overlay sheet ../proof/overlay_qnn_vs_ort.png."""
import numpy as np, glob, os, json, cv2, onnxruntime as ort, sys
sys.path.insert(0, ".."); import posepipe as P
s = ort.InferenceSession("onnx/rtmpose_body2d.onnx"); fr = sorted(glob.glob("../proof/frames/f*.raw")); n = len(fr)
def dec(px, py): return np.stack([px[:17].argmax(1) / 2.0, py[:17].argmax(1) / 2.0], 1), np.minimum(px[:17].max(1), py[:17].max(1))
ref = []
for f in fr:
    x = np.fromfile(f, "<f4").reshape(1, 3, 256, 192); r = s.run(None, {"image": x}); ref.append(dec(r[0][0], r[1][0]))
def load(tag, k):
    if tag.startswith("qnn"): a, b = f"../proof/out_{tag}/output_{k}_0.raw", f"../proof/out_{tag}/output_{k}_1.raw"
    else: a, b = f"../proof/out_{tag}/f{k:02d}-0.bin", f"../proof/out_{tag}/f{k:02d}-1.bin"
    return dec(np.fromfile(a, "<f4").reshape(133, 384), np.fromfile(b, "<f4").reshape(133, 512))
out = {}; thr = 0.05 * 256
for tag in ["qnn_fp16", "xnnpack_fp32", "xnnpack_int8"]:
    if not os.path.isdir(f"../proof/out_{tag}"): continue
    errs, pck, cdiff = [], [], []
    for k in range(n):
        xy, c = load(tag, k); rxy, rc = ref[k]; m = rc >= 0.3
        e = np.linalg.norm(xy - rxy, axis=1); errs += e[m].tolist(); pck += (e[m] < thr).tolist(); cdiff += np.abs(c - rc).tolist()
    out[tag] = {"frames": n, "joints_evaluated": len(errs), "mean_px_err_crop": float(np.mean(errs)), "median_px_err_crop": float(np.median(errs)), "max_px_err_crop": float(np.max(errs)), "pck@0.05": float(np.mean(pck)), "mean_abs_conf_diff": float(np.mean(cdiff))}
    print(tag, out[tag])
json.dump(out, open("../proof/agreement.json", "w"), indent=1)
tiles = []
for k in range(0, n, 2):
    im = cv2.imread(f"../proof/frames/f{k:02d}.png"); xy, c = load("qnn_fp16", k); rxy, rc = ref[k]
    for a, b in P.COCO_BONES: cv2.line(im, tuple(map(int, rxy[a])), tuple(map(int, rxy[b])), (0, 200, 255), 2, cv2.LINE_AA)
    for q in range(17):
        cv2.circle(im, tuple(map(int, rxy[q])), 4, (0, 200, 255), 1, cv2.LINE_AA); cv2.circle(im, tuple(map(int, xy[q])), 2, (0, 255, 0), -1, cv2.LINE_AA)
    tiles.append(im)
sheet = np.concatenate([np.concatenate(tiles[:5], 1), np.concatenate(tiles[5:10], 1)], 0)
cv2.putText(sheet, "orange=onnxruntime fp32 (Mac)  green=ExecuTorch QNN fp16 on Ventuno HTP", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
cv2.imwrite("../proof/overlay_qnn_vs_ort.png", sheet); print("wrote ../proof/overlay_qnn_vs_ort.png")
