"""Two-stage MediaPipe pose on the Ventuno NPU, driven from the Mac over adb.

Mac: frame extraction, letterbox/crop preprocessing, anchor decode, drawing.
Board (qnn-net-run, HTP): pose_detector.bin (128x128) and pose_landmark_detector.bin (256x256).
"""
import argparse, json, math, os, shutil, subprocess, sys, time
import cv2, numpy as np

BOARD_DIR = "/home/arduino/models/mp62"
ENV = 'export ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib" LD_LIBRARY_PATH=/usr/lib;'


def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def extract_frames(video, t0, t1, fps, outdir):
    os.makedirs(outdir, exist_ok=True)
    sh(f'ffmpeg -v error -y -ss {t0} -t {t1 - t0} -i "{video}" -vf fps={fps} "{outdir}/f%05d.png"')
    return sorted(os.path.join(outdir, f) for f in os.listdir(outdir) if f.endswith(".png"))


def letterbox(img, size):
    h, w = img.shape[:2]
    s = size / max(h, w)
    nh, nw = round(h * s), round(w * s)
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((size, size, 3), np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = r
    return canvas, s, left, top


def run_batch(model, arrays, work, tag):
    """arrays: list of float32 NHWC arrays. Returns list of dict(name -> np.ndarray)."""
    d = os.path.join(work, tag)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    names = []
    for i, a in enumerate(arrays):
        n = f"in_{i:05d}.raw"
        a.astype("<f4").tofile(os.path.join(d, n))
        names.append(n)
    open(os.path.join(d, "list.txt"), "w").write("\n".join(names) + "\n")
    rdir = f"{BOARD_DIR}/run_{tag}"
    sh(f"adb shell 'rm -rf {rdir}; mkdir -p {rdir}'")
    sh(f"adb push {d}/. {rdir}/ >/dev/null")
    t = time.time()
    out = sh(f"adb shell '{ENV} cd {rdir} && qnn-net-run --backend /usr/lib/libQnnHtp.so "
             f"--retrieve_context {model if model.startswith("/") else BOARD_DIR + "/" + model + ".bin"} --input_list list.txt --output_dir out 2>&1 | grep -E \"Finished|fail|Fail\"'")
    dt = time.time() - t
    if "Finished" not in out:
        raise RuntimeError(out)
    print(f"  [{tag}] {len(arrays)} inferences on NPU, wall {dt:.1f}s ({len(arrays) / dt:.0f}/s incl. process+context load)")
    od = os.path.join(d, "out")
    sh(f"adb pull {rdir}/out {od} >/dev/null")
    results = []
    for i in range(len(arrays)):
        rd = os.path.join(od, f"Result_{i}")
        results.append({f[:-4]: np.fromfile(os.path.join(rd, f), "<f4") for f in os.listdir(rd) if f.endswith(".raw")})
    return results


# ---- detector decode (MediaPipe SSD, 128 input, strides 8,16,16,16, 2 anchors/cell) ----
def make_anchors():
    a = []
    for fm, per in ((16, 2), (8, 6)):
        for y in range(fm):
            for x in range(fm):
                for _ in range(per):
                    a.append(((x + 0.5) / fm, (y + 0.5) / fm))
    return np.array(a, np.float32)  # 896 x 2


ANCHORS = make_anchors()


def decode_detections(res, score_thr=0.5):
    scores = np.concatenate([res["box_scores_1"], res["box_scores_2"]])
    raw = np.concatenate([res["box_coords_1"].reshape(-1, 12), res["box_coords_2"].reshape(-1, 12)])
    scores = 1 / (1 + np.exp(-np.clip(scores, -100, 100)))
    dets = []
    for i in np.where(scores >= score_thr)[0]:
        ax, ay = ANCHORS[i]
        r = raw[i] / 128.0
        cx, cy, w, h = r[0] + ax, r[1] + ay, r[2], r[3]
        kps = [(r[4 + 2 * k] + ax, r[5 + 2 * k] + ay) for k in range(4)]
        dets.append((float(scores[i]), cx, cy, w, h, kps))
    dets.sort(key=lambda d: -d[0])
    keep = []
    for d in dets:  # simple NMS on boxes
        ok = True
        for k in keep:
            ix = max(0, min(d[1] + d[3] / 2, k[1] + k[3] / 2) - max(d[1] - d[3] / 2, k[1] - k[3] / 2))
            iy = max(0, min(d[2] + d[4] / 2, k[2] + k[4] / 2) - max(d[2] - d[4] / 2, k[2] - k[4] / 2))
            inter = ix * iy
            if inter / (d[3] * d[4] + k[3] * k[4] - inter + 1e-9) > 0.3:
                ok = False
                break
        if ok:
            keep.append(d)
    return keep


def roi_from_detection(det, s, left, top, size=128, scale=1.25):
    """BlazePose ROI: centre = kp2 (body centre), size = 2*|kp3-kp2|*scale, rotated so kp2->kp3 points up.
    Returns (cx, cy, side, rot) with rot = angle of the 'up' axis in frame px."""
    to_px = lambda p: ((p[0] * size - left) / s, (p[1] * size - top) / s)
    (x0, y0), (x1, y1) = to_px(det[5][2]), to_px(det[5][3])
    side = 2 * math.hypot(x1 - x0, y1 - y0) * scale
    rot = math.atan2(y1 - y0, x1 - x0)  # direction of up axis
    return float(x0), float(y0), float(side), float(rot)


def roi_matrix(roi, out=256):
    cx, cy, side, rot = roi
    u = np.array([math.cos(rot), math.sin(rot)])      # crop "up" in frame px
    r = np.array([-u[1], u[0]])                        # crop "right"... (for up=(0,-1) -> (1,0))
    r = np.array([u[1] * -1, u[0]]) if False else np.array([-u[1], u[0]])
    A = (side / out) * np.stack([r, -u], 1)            # out px -> frame px (linear part)
    t = np.array([cx, cy]) - A @ np.array([out / 2, out / 2])
    return np.concatenate([A, t[:, None]], 1).astype(np.float32)


def crop_roi(img, roi, out=256):
    M = roi_matrix(roi, out)
    crop = cv2.warpAffine(img, M, (out, out), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR, borderValue=0)
    return crop, M


def landmarks_to_frame(lm, M, out=256):
    pts = lm.reshape(-1, 4)
    xy = np.stack([pts[:, 0] * out, pts[:, 1] * out, np.ones(len(pts))], 1) @ M.T
    return np.concatenate([xy, pts[:, 2:]], 1)  # x,y in frame px, z, vis


# ---- RTMPose-m (COCO-wholebody 256x192, SimCC) top-down stage ----
RTM_BIN = "/home/arduino/models/rtm/gen/rtmpose_v75.bin"
COCO17 = ["nose","l_eye","r_eye","l_ear","r_ear","l_sho","r_sho","l_elb","r_elb","l_wri","r_wri","l_hip","r_hip","l_kne","r_kne","l_ank","r_ank"]
COCO_BONES = [(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16),(0,5),(0,6)]


def rtm_matrix(roi, out_w=192, out_h=256, h_frac=1.3):
    """Frame-px affine for an RTMPose crop from a MediaPipe body-circle ROI (cx,cy,side,rot)."""
    cx, cy, side, rot = roi
    H = side * h_frac; W = H * out_w / out_h
    u = np.array([math.cos(rot), math.sin(rot)]); r = np.array([-u[1], u[0]])
    A = np.stack([r * (W / out_w), -u * (H / out_h)], 1)
    t = np.array([cx, cy]) - A @ np.array([out_w / 2, out_h / 2])
    return np.concatenate([A, t[:, None]], 1).astype(np.float32)


def rtm_crop(img_rgb, roi):
    M = rtm_matrix(roi)
    crop = cv2.warpAffine(img_rgb, M, (192, 256), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR, borderValue=0)
    return crop, M


def rtm_input(crop, bgr=True):  # HWC uint8 RGB -> 1x3x256x192 float32 in 0..255 (model normalises internally)
    x = crop.astype(np.float32).transpose(2, 0, 1)[None]
    return x[:, ::-1].copy() if bgr else x


def rtm_decode(res, M, n=17):
    px, py = res["pred_x"].reshape(133, 384)[:n], res["pred_y"].reshape(133, 512)[:n]
    xs, ys = px.argmax(1) / 2.0, py.argmax(1) / 2.0   # SimCC split ratio 2 -> crop px
    sc = np.minimum(px.max(1), py.max(1))
    xy = np.stack([xs, ys, np.ones(n)], 1) @ M.T
    return xy, sc  # frame px, per-joint confidence


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--t0", type=float, default=0); ap.add_argument("--t1", type=float, default=10)
    ap.add_argument("--fps", type=float, default=8); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    work = os.path.join(a.out, "work")
    print("extracting frames...")
    paths = extract_frames(a.video, a.t0, a.t1, a.fps, os.path.join(work, "frames"))
    imgs = [cv2.imread(p) for p in paths]  # BGR
    print(f"  {len(imgs)} frames, {imgs[0].shape[1]}x{imgs[0].shape[0]}")

    lb = [letterbox(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), 128) for im in imgs]
    det_res = run_batch("pose_detector", [(x[0].astype(np.float32) / 255.0)[None] for x in lb], work, "det")
    rois, dets = [], []
    for res, (_, s, left, top) in zip(det_res, lb):
        ds = decode_detections(res)
        dets.append(ds[0] if ds else None)
        rois.append(roi_from_detection(ds[0], s, left, top) if ds else None)
    print(f"  detections: {sum(r is not None for r in rois)}/{len(rois)} frames")

    idx = [i for i, r in enumerate(rois) if r is not None]
    crops = [crop_roi(cv2.cvtColor(imgs[i], cv2.COLOR_BGR2RGB), rois[i]) for i in idx]
    lm_res = run_batch("pose_landmark_detector", [(c[0].astype(np.float32) / 255.0)[None] for c in crops], work, "lm")
    out = {"fps": a.fps, "t0": a.t0, "frames": []}
    for n in range(len(imgs)):
        out["frames"].append({"i": n, "roi": rois[n], "det_score": dets[n][0] if dets[n] else None, "landmarks": None, "pose_score": None})
    for j, i in enumerate(idx):
        res = lm_res[j]
        out["frames"][i]["landmarks"] = landmarks_to_frame(res["landmarks"], crops[j][1]).tolist()
        out["frames"][i]["pose_score"] = float(res["scores"][0])
    json.dump(out, open(os.path.join(a.out, "keypoints.json"), "w"))
    print("wrote", os.path.join(a.out, "keypoints.json"))


if __name__ == "__main__":
    main()
