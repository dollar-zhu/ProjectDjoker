"""Lower RTMPose-m to a QNN(HTP)-delegated ExecuTorch .pte ON THE VENTUNO Q itself (aarch64 AOT: the board has
libQnnHtpPrepare.so and a teammate-built PyQnnManagerAdaptor for py3.12). Expects ~/et-venv with executorch==1.5.0
+ the on-board PyQnnManagerAdaptor copied into site-packages (see docs/board-status.md).
Usage: QNN_SDK_ROOT=~/qairt-fake LD_LIBRARY_PATH=/usr/lib python export_qnn_onboard.py [--soc QCS8275] [--tiny] [--out X]"""
import argparse, time, torch, sys
from executorch.backends.qualcomm.utils.utils import generate_htp_compiler_spec, generate_qnn_executorch_compiler_spec, to_edge_transform_and_lower_to_qnn
from executorch.backends.qualcomm.serialization.qc_schema import QcomChipset
ap = argparse.ArgumentParser(); ap.add_argument("--soc", default="QCS8275"); ap.add_argument("--tiny", action="store_true"); ap.add_argument("--out", default=None); ap.add_argument("--ep", default="rtmpose_ep.pt2"); a = ap.parse_args()
if a.tiny:
    class M(torch.nn.Module):
        def __init__(s): super().__init__(); s.c = torch.nn.Conv2d(3, 8, 3, padding=1)
        def forward(s, x): return torch.relu(s.c(x)).mean((2, 3))
    model, inputs = M().eval(), (torch.rand(1, 3, 32, 32),)
else:
    model, inputs = torch.export.load(a.ep).module(), (torch.rand(1, 3, 256, 192) * 255,)
out = a.out or ("tiny_qnn_%s.pte" % a.soc if a.tiny else "rtmpose_qnn_fp16_%s.pte" % a.soc)
t0 = time.time()
spec = generate_qnn_executorch_compiler_spec(soc_model=getattr(QcomChipset, a.soc), backend_options=generate_htp_compiler_spec(use_fp16=True))
edge = to_edge_transform_and_lower_to_qnn(model, inputs, spec)
gm = edge.exported_program().graph_module
ops = [n.target for n in gm.graph.nodes if n.op == "call_function"]
print("delegate calls:", sum("executorch_call_delegate" in str(o) for o in ops), "| non-delegated:", [str(o) for o in ops if "executorch_call_delegate" not in str(o) and "getitem" not in str(o)])
et = edge.to_executorch(); open(out, "wb").write(et.buffer); print("wrote", out, round(len(et.buffer) / 1e6, 1), "MB in", round(time.time() - t0, 1), "s")
