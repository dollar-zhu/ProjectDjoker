# ExecuTorch export of RTMPose-m for the Ventuno Q

Scripts here lower RTMPose-Body2d (AI Hub ONNX, 1x3x256x192, SimCC heads) to ExecuTorch `.pte` files and prove them on the board. Full write-up and measured numbers: `docs/board-status.md`; agreement/latency results: `../proof/{bench,agreement}.json`.

Python env: `.venv-et/` (py3.12, executorch 1.5.0, torch 2.14.1, torchao, onnx2torch, onnxruntime; ignored). On the board: `~/et-venv` plus the teammate-built `PyQnnManagerAdaptor` (see `docs/board-status.md`). The `.pte` files live on the board at `~/models/et/`.

`boardsrc/serialization/` is **not** plain upstream: it is executorch 1.5.0's `backends/qualcomm/serialization` with `QcomChipset.QCS8275 = 82` (HTP v75) added to `qc_schema.py` and `qc_compiler_spec.fbs`. Copy it over the board's site-packages before running `export_qnn_onboard.py`.

## Ignored artefacts and how to regenerate them

All paths relative to this directory unless noted. Everything below is git-ignored (`*.pte *.pt *.pt2 *.onnx *.etdp *.bin *.raw *.npy *.mp4`, `onnx/ calib/ eval_work/ out_qnn/`, `../proof/frames/ ../proof/out_*/`).

| Artefact | Size | Regenerate |
|---|---|---|
| `onnx/rtmpose_body2d.onnx` + `.data`, `metadata.json` | 81 MB | Download the RTMPose-Body2d ONNX export from Qualcomm AI Hub (`qairt 2.50.0` metadata); no script, it is the input. |
| `rtmpose_torch.pt` | 69 MB | `.venv-et/bin/python -c "import torch, onnx2torch; torch.save(onnx2torch.convert('onnx/rtmpose_body2d.onnx'), 'rtmpose_torch.pt')"` (ad hoc; no script committed). |
| `rtmpose_torch_static.pt` | 85 MB | `.venv-et/bin/python make_static.py` (replaces data-dependent onnx2torch ops with `static_ops.py` equivalents; checks max diff 0 and `torch.export`). |
| `rtmpose_ep.pt2` | 69 MB | `.venv-et/bin/python -c "import torch, static_ops; t=torch.load('rtmpose_torch_static.pt', weights_only=False).eval(); torch.export.save(torch.export.export(t, (torch.rand(1,3,256,192)*255,)), 'rtmpose_ep.pt2')"`, then `adb push rtmpose_ep.pt2 /home/arduino/models/et/`. |
| `rtmpose_qnn_fp16_QCS8275.pte` | 37 MB | On the board: `source ~/et-venv/bin/activate; cd ~/models/et; QNN_SDK_ROOT=~/qairt-fake LD_LIBRARY_PATH=/usr/lib python export_qnn_onboard.py --soc QCS8275` (`--tiny` for a 1-conv smoke model); `adb pull` it back here. fp16 on HTP, not int8. |
| `rtmpose_xnnpack_fp32.pte` | 69 MB | `.venv-et/bin/python export_xnnpack.py` |
| `rtmpose_xnnpack_int8.pte` | 19 MB | `.venv-et/bin/python export_xnnpack.py --int8 --out rtmpose_xnnpack_int8.pte` (PT2E, per-channel symmetric, calibrated on `calib/*.npy`). |
| `../proof/frames/` (`fNN.raw`, `fNN.png`, `srcNN.png`, `MNN.npy`), `calib/*.npy`, `eval_work/det/` | 27 + 11 + 5 MB | `cd ..; python proof/make_frames.py` (needs `nvidia_serve_overlay.mp4` next to `posepipe.py` and the board reachable over adb for the MediaPipe detector). Then `adb push proof/frames/*.raw /home/arduino/models/et/frames/`. |
| `../proof/out_qnn_fp16/`, `../proof/out_xnnpack_*/`, `../proof/qnn_fp16.etdp`, `../proof/bench.json` | 9 MB each | `.venv-et/bin/python bench_board.py [qnn_fp16 xnnpack_fp32 xnnpack_int8]` (board over adb; runners at `~/git/executorch/build-x86/.../qnn_executor_runner` and `~/git/executorch/build-xnnpack/executor_runner`). `bench.json` is committed. |
| `../proof/agreement.json`, `../proof/overlay_qnn_vs_ort.png` | small, committed | `.venv-et/bin/python proof_report.py` (after `bench_board.py`; needs `onnx/` and `../proof/frames/`). |
| `in.raw`, `out_fp32-*.bin`, `out_qnn/`, `rtm_qnn.etdp` | <1 MB | Scratch from the first manual runner invocations (`docs/board-status.md`, "Running on the board"); safe to delete. |
| `../proof/qnn_fp16_etdump_ops.csv` | 24 KB, committed | Per-op table from the QNN ETDump (`qnn_fp16.etdp`) via executorch's `Inspector`; ad hoc, no script. |

Limitations: `rtmpose_torch.pt` and `rtmpose_ep.pt2` were produced interactively, so the one-liners above reconstruct the steps described in `docs/board-status.md` rather than reproduce a committed script. No int8 QNN path yet.
