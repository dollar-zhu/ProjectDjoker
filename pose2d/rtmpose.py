"""Minimal RTMPose (SimCC, top-down) ONNX runner with explicit, recorded preprocessing.

Mirrors the model's own mmdeploy pipeline.json: bbox padding 1.25, aspect-fixed affine crop,
BGR->RGB (to_rgb: true), ImageNet mean/std, SimCC argmax decode with split ratio 2.0.
No person detector: the caller supplies the crop box (fixed operator crop for now).
"""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
import numpy as np
import cv2
import onnxruntime as ort

MODELS = {
    'rtmpose-m-body7-256x192': dict(
        url='https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-m_simcc-body7_pt-body7_420e-256x192-e48f03d0_20230504.zip',
        zip_sha256='f7fbb6c5c11a1bb70f3d445e4ddec5d144ea89ad5649c081ef976f9b24a0b741',
        onnx_sha256='5c0a4bf67953e6d2ac43ce15e77dc9d5d354ae18430a47d2c5963a7bc5683e3c'),
}
# RTMPose body7 emits COCO-17 keypoints, which is the DMS canonical17 order.
COCO17_EVIDENCE = 'https://github.com/open-mmlab/mmpose/blob/main/configs/_base_/datasets/coco.py'

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()

def fetch_model(name, cache_dir):
    """Download once, verify both archive and ONNX hashes; offline after the first run."""
    spec = MODELS[name]; cache_dir = Path(cache_dir); target = cache_dir / name
    onnx_path = target / 'end2end.onnx'
    if not onnx_path.exists():
        target.mkdir(parents=True, exist_ok=True); archive = target / 'model.zip'
        if not archive.exists(): urllib.request.urlretrieve(spec['url'], archive)
        if sha256(archive) != spec['zip_sha256']: raise RuntimeError(f'{archive}: archive checksum differs')
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():
                base = Path(member).name
                if base in ('end2end.onnx', 'pipeline.json', 'deploy.json', 'detail.json'):
                    (target / base).write_bytes(z.read(member))
    if sha256(onnx_path) != spec['onnx_sha256']: raise RuntimeError(f'{onnx_path}: ONNX checksum differs')
    return target

class RTMPose:
    def __init__(self, model_dir, providers=('CPUExecutionProvider',)):
        model_dir = Path(model_dir); onnx_path = model_dir / 'end2end.onnx'
        tasks = json.loads((model_dir / 'pipeline.json').read_text())['pipeline']['tasks']
        transforms = {t['type']: t for t in tasks[0]['transforms']}
        decode = tasks[2]['params']
        self.padding = transforms['TopDownGetBboxCenterScale']['padding']
        self.input_wh = tuple(transforms['TopDownAffine']['image_size'])
        norm = transforms['Normalize']
        self.mean = np.array(norm['mean'], np.float32); self.std = np.array(norm['std'], np.float32)
        self.to_rgb = bool(norm['to_rgb']); self.split_ratio = float(decode['simcc_split_ratio'])
        if decode.get('use_dark') or decode.get('flip_test'): raise RuntimeError('Unsupported decode options')
        self.session = ort.InferenceSession(str(onnx_path), providers=list(providers))
        shape = self.session.get_inputs()[0].shape
        if tuple(shape[2:]) != (self.input_wh[1], self.input_wh[0]): raise RuntimeError(f'ONNX input {shape} disagrees with pipeline')
        self.info = {
            'model': model_dir.name, 'runtime': 'onnxruntime', 'runtime_version': ort.__version__,
            'providers_requested': list(providers), 'providers_active': self.session.get_providers(),
            'onnx_sha256': sha256(onnx_path), 'input_shape': shape,
            'outputs': [[o.name, o.shape] for o in self.session.get_outputs()],
            'preprocess': {'bbox_padding': self.padding, 'input_wh': list(self.input_wh), 'to_rgb': self.to_rgb,
                           'mean': norm['mean'], 'std': norm['std'], 'aspect_fix': 'expand shorter side to input aspect',
                           'interpolation': 'cv2.INTER_LINEAR'},
            'decode': {'method': 'simcc_argmax', 'simcc_split_ratio': self.split_ratio, 'normalize': decode.get('normalize'),
                       'score': 'mean(max(simcc_x), max(simcc_y)); raw logit peak, not a probability'},
        }

    def crop_transform(self, box_xyxy):
        """Center/size of the region actually fed to the model, in original pixels."""
        x1, y1, x2, y2 = map(float, box_xyxy); w, h = (x2 - x1) * self.padding, (y2 - y1) * self.padding
        aspect = self.input_wh[0] / self.input_wh[1]
        w, h = (w, w / aspect) if w > h * aspect else (h * aspect, h)
        return np.array([(x1 + x2) / 2, (y1 + y2) / 2]), np.array([w, h])

    def estimate(self, image_bgr, box_xyxy):
        """Returns keypoints (17,2) in original image pixels and raw scores (17,)."""
        center, size = self.crop_transform(box_xyxy); W, H = self.input_wh; k = W / size[0]
        warp = np.array([[k, 0, W / 2 - k * center[0]], [0, k, H / 2 - k * center[1]]], np.float32)
        crop = cv2.warpAffine(image_bgr, warp, (W, H), flags=cv2.INTER_LINEAR)
        if self.to_rgb: crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = ((crop.astype(np.float32) - self.mean) / self.std).transpose(2, 0, 1)[None]
        simcc_x, simcc_y = self.session.run(None, {self.session.get_inputs()[0].name: np.ascontiguousarray(tensor)})
        return decode_simcc(simcc_x[0], simcc_y[0], self.split_ratio, center, size, self.input_wh)

def decode_simcc(simcc_x, simcc_y, split_ratio, center, size, input_wh):
    loc = np.stack([simcc_x.argmax(1), simcc_y.argmax(1)], -1).astype(np.float64) / split_ratio
    scores = 0.5 * (simcc_x.max(1) + simcc_y.max(1))
    # Invert the crop: model-input pixels -> original image pixels (uniform scale, no rotation).
    keypoints = center + (loc - np.asarray(input_wh) / 2) * (size[0] / input_wh[0])
    return keypoints, scores.astype(np.float64)
