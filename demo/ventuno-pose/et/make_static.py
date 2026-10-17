"""Turn the onnx2torch RTMPose module into a torch.export-able module: data-dependent onnx2torch ops (Reshape,
Squeeze, Split, GatherND with constant shape/index inputs) are replaced by static equivalents recorded from one
forward pass. Writes rtmpose_torch_static.pt."""
import torch, torch.nn as nn
t = torch.load("rtmpose_torch.pt", weights_only=False).eval(); x = torch.rand(1, 3, 256, 192) * 255
DYN = ("OnnxReshape", "OnnxSqueezeDynamicAxes", "OnnxSplit13", "OnnxGatherND")
rec = {}
def pre(mod, inp, n): rec.setdefault(n, {})["in"] = inp
def post(mod, inp, out, n): rec[n]["out"] = out
hooks = []
for n, m in t.named_modules():
    if type(m).__name__ in DYN: hooks += [m.register_forward_pre_hook(lambda mod, inp, n=n: pre(mod, inp, n)), m.register_forward_hook(lambda mod, inp, out, n=n: post(mod, inp, out, n))]
with torch.no_grad(): y0 = t(x)
for h in hooks: h.remove()
from static_ops import StaticReshape, StaticSplit, StaticGatherND
for n, r in rec.items():
    m = t.get_submodule(n); kind = type(m).__name__
    if kind in ("OnnxReshape", "OnnxSqueezeDynamicAxes"): new = StaticReshape(tuple(r["out"].shape))
    elif kind == "OnnxSplit13":
        outs = r["out"]; axis = m.axis if hasattr(m, "axis") else [d for d in range(r["in"][0].dim()) if r["in"][0].shape[d] != outs[0].shape[d]][0]
        new = StaticSplit([o.shape[axis] for o in outs], axis)
    elif kind == "OnnxGatherND": new = StaticGatherND(r["in"][1])
    parent = t.get_submodule(n.rsplit(".", 1)[0]) if "." in n else t; setattr(parent, n.rsplit(".", 1)[-1], new); print("replaced", n, kind, "->", new)
with torch.no_grad(): y1 = t(x)
print("max diff after static rewrite:", [float((a - b).abs().max()) for a, b in zip(y0, y1)])
torch.export.export(t, (x,)); print("torch.export ok"); torch.save(t, "rtmpose_torch_static.pt")
