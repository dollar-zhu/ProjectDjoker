"""Static replacements for data-dependent onnx2torch ops (see make_static.py); importable so the pickled model loads."""
import torch, torch.nn as nn
class StaticReshape(nn.Module):
    def __init__(s, shape): super().__init__(); s.shape = shape
    def forward(s, inp, *a): return inp.reshape(s.shape)
class StaticSplit(nn.Module):
    def __init__(s, sizes, axis): super().__init__(); s.sizes, s.axis = sizes, axis
    def forward(s, inp, *a): return torch.split(inp, s.sizes, dim=s.axis)
class StaticGatherND(nn.Module):
    def __init__(s, idx): super().__init__(); [s.register_buffer(f"i{k}", idx[..., k].long()) for k in range(idx.shape[-1])]; s.k = idx.shape[-1]
    def forward(s, inp, *a): return inp[tuple(getattr(s, f"i{k}") for k in range(s.k))]
