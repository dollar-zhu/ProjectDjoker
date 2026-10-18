"""Export RTMPose-m (COCO-wholebody 256x192, from the AI Hub ONNX via onnx2torch) to an XNNPACK-delegated
ExecuTorch .pte. Run with .venv-et (executorch==1.5.0). Usage: python export_xnnpack.py [--int8] [--out X.pte]"""
import argparse, sys, time, torch, numpy as np, static_ops
from executorch.exir import to_edge_transform_and_lower, EdgeCompileConfig
from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
ap = argparse.ArgumentParser(); ap.add_argument("--int8", action="store_true"); ap.add_argument("--out", default="rtmpose_xnnpack_fp32.pte"); a = ap.parse_args()
t = torch.load("rtmpose_torch_static.pt", weights_only=False).eval(); x = (torch.rand(1, 3, 256, 192) * 255,)
t0 = time.time()
if a.int8:
    from torchao.quantization.pt2e.quantize_pt2e import prepare_pt2e, convert_pt2e
    from executorch.backends.xnnpack.quantizer.xnnpack_quantizer import XNNPACKQuantizer, get_symmetric_quantization_config
    ex = torch.export.export(t, x).module(); q = XNNPACKQuantizer(); q.set_global(get_symmetric_quantization_config(is_per_channel=True))
    p = prepare_pt2e(ex, q)
    import glob, cv2
    for f in sorted(glob.glob("calib/*.npy"))[:32]: p(torch.from_numpy(np.load(f)))
    if not glob.glob("calib/*.npy"): p(*x)
    t = convert_pt2e(p)
ep = torch.export.export(t, x)
edge = to_edge_transform_and_lower(ep, partitioner=[XnnpackPartitioner()], compile_config=EdgeCompileConfig(_check_ir_validity=False))
print(edge.exported_program().graph_module.code[:3000])
et = edge.to_executorch(); open(a.out, "wb").write(et.buffer)
print("wrote", a.out, len(et.buffer) / 1e6, "MB in", round(time.time() - t0, 1), "s")
