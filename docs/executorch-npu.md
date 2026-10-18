# ExecuTorch on the Ventuno Q NPU: export, runtime and profiling evidence

This document records how Djoker's models run on the Arduino VENTUNO Q through ExecuTorch, and the profiling evidence that they actually run on the Hexagon NPU. A successful model load is not treated as proof. Each claim below cites a committed artifact or a reproducible command.

Board: Arduino VENTUNO Q, Qualcomm Dragonwing QCS8275 (Hexagon HTP v75, 8 CPU cores, 15 GB RAM), Ubuntu 24.04 aarch64, Python 3.12.3. A USB-attached STM32H5 MCU is exposed to Linux through the Arduino Router ("Bridge").

## Summary

| Model | Role | ExecuTorch backend | Where it runs | Measured |
|---|---|---|---|---|
| RTMPose-m (COCO-WholeBody, 133 keypoints, SimCC heads), `rtmpose_qnn_fp16_QCS8275.pte` | 2D pose per frame | QNN, HTP, fp16 | Hexagon NPU | **6.45 ms/frame** (20 crops, warm), 4.49 ms hot loop, **50 MB** peak RSS, 222 ms method load |
| Same model, `rtmpose_xnnpack_int8.pte` | CPU fallback / comparison | XNNPACK int8 | Kryo CPU, 8 threads | 27.9 ms (p95 33), 41 MB |
| Same model, `rtmpose_xnnpack_fp32.pte` | CPU baseline | XNNPACK fp32 | Kryo CPU, 4 threads | 85.9 ms (p95 182), 140 MB |
| Gemma 3 1B, `gemma3-1b_qcs8275_ctxt-5000.pte` | Rephrases one approved coaching cue | QNN (`qnn_llama_runner`) | Hexagon NPU | prefill 508–627 tok/s, decode ~30 tok/s, TTFT 59–65 ms, 1.31 GB RSS |
| Piper `en_US-*-medium` | Speech | onnxruntime (CPU), **not ExecuTorch** | CPU | ~real-time as a one-shot process on the board |

On the NPU, RTMPose is **4.3× faster than the fastest CPU configuration** (XNNPACK int8, 8 threads: 27.9 ms → 6.45 ms) without int8's accuracy loss. Against the same-precision CPU path (XNNPACK fp32, 85.9 ms at its best thread count) it is **13× faster at about a third of the memory**. NPU fp16 keeps PCK@0.05 = 1.000 against the fp32 reference; CPU int8 drops to 0.995.

## 1. Proof that RTMPose runs on the NPU

### ETDump operator profile

Source: `demo/ventuno-pose/proof/qnn_fp16_etdump_ops.csv`, produced from an ETDump captured with `qnn_executor_runner --profile_level 2 --etdump_path qnn_fp16.etdp`. That run covered 20 frames × (1 iteration + 2 warm-ups), or 60 executions. The table was extracted with ExecuTorch's `Inspector`.

- **Delegation:** the Execute block has 302 rows. **300 are QNN-delegated.** The two non-delegated rows are the `Method::execute` and `DELEGATE_CALL` wrappers (6.55 ms average each). **No operator falls back to the CPU; the whole graph is one QNN delegate.**
- **Operators on the HTP:** 288 operators: mul 72, convolution 62, sigmoid 58 (SiLU = mul + sigmoid), view_copy 20, add 16, permute_copy 13, matmul 7 (SimCC heads / GAU attention), clamp 6, cat 5, div 4, mean_dim 4, pow 4, constant_pad_nd 3, max_pool2d 3, plus a few singletons.
- **HTP timers (average per execution):** QNN execute 6.14 ms, RPC execute 5.66 ms, **accelerator execute 4.17 ms**, 6.81 M accelerator cycles, 4 HVX threads, VTCM acquire 0.17 ms, HVX+HMX power-on 0.23 ms, 0 yields. `Method::init` (context-binary load) takes 219.7 ms.
- **Hot spots:** the model's built-in mean/std input normalization (`aten_sub_tensor:OpId_74` ≈15%, `aten_div_tensor:OpId_75` ≈12% of accelerator cycles) and one 1×1 convolution (`OpId_742`, ≈12%). Folding the normalization into the first convolution would remove roughly a quarter of HTP cycles. This optimization is identified but not yet implemented.

Re-check the delegation count from the committed CSV:

```sh
python3 - <<'EOF'
import csv
rows = [r for r in csv.DictReader(open('demo/ventuno-pose/proof/qnn_fp16_etdump_ops.csv')) if r['event_block_name'] == 'Execute']
print(len(rows), 'execute rows;', sum(r['is_delegated_op'] == 'True' for r in rows), 'QNN-delegated')
print('non-delegated:', [r['event_name'] for r in rows if r['is_delegated_op'] == 'False'])
EOF
```

### Latency and memory (`demo/ventuno-pose/proof/bench.json`)

Produced by `demo/ventuno-pose/et/bench_board.py` over adb, using 20 real serve crops (1×3×256×192 float32).

| `.pte` | Backend | Per frame, 20 crops | Hot loop (50 iterations, 1 frame) | Peak RSS | Load |
|---|---|---|---|---|---|
| `rtmpose_qnn_fp16_QCS8275.pte` | QNN HTP fp16 | **6.45 ms** (6.3–6.7) | 4.49 ms | **50 MB** | 222 ms |
| `rtmpose_xnnpack_fp32.pte` | XNNPACK CPU, default threads | 198 ms (121–235) | 201 ms (p95 228) | 140 MB | 193 ms |
| same, `--cpu_threads 4` / `8` | | | 85.9 ms (p95 182) / 111 ms (p95 128) | | |
| `rtmpose_xnnpack_int8.pte` | XNNPACK CPU, default threads | 77 ms (69–85) | 80 ms (p95 90) | 41 MB | 79 ms |
| same, `--cpu_threads 4` / `8` | | | 37.9 ms (p95 61) / **27.9 ms** (p95 33) | | |

Default-thread XNNPACK numbers come from short runs while other adb jobs were active and are noisy; use the `--cpu_threads` rows for CPU comparisons.

A second, larger run on real tennis footage (`benchmark/manual/samples/README.md`): **230/230** frames from three amateur and pro clips completed on the NPU, with a **mean reported model inference of 4.46 ms/crop (p95 4.73 ms)** and 49.9 MiB peak RSS.

### Accuracy vs the fp32 reference (`demo/ventuno-pose/proof/agreement.json`)

Produced by `demo/ventuno-pose/et/proof_report.py`, compared with onnxruntime fp32 on the Mac. The evaluation covers 17 COCO body joints with ORT confidence ≥ 0.3: 193 joints over 20 crops. The PCK threshold is 0.05 × 256 = 12.8 px.

| Run | Mean px error | Median | Max | PCK@0.05 | Mean abs confidence diff |
|---|---|---|---|---|---|
| QNN fp16 (NPU) | 0.24 | 0.0 | 1.12 | **1.000** | 0.006 |
| XNNPACK fp32 | 0.00 | 0.0 | 0.00 | 1.000 | 5e-7 |
| XNNPACK int8 | 1.22 | 0.71 | 13.5 | 0.995 | 0.020 |

Visual check: `demo/ventuno-pose/proof/overlay_qnn_vs_ort.png` (orange = onnxruntime fp32 on the Mac, green = ExecuTorch QNN on the NPU).

![QNN vs ORT overlay](../demo/ventuno-pose/proof/overlay_qnn_vs_ort.png)

## 2. How the `.pte` files were produced

Scripts are in `demo/ventuno-pose/et/` (see its [README](../demo/ventuno-pose/et/README.md) for the full regeneration table). Model binaries are git-ignored.

Toolchain:

| Where | What |
|---|---|
| Mac `demo/ventuno-pose/et/.venv-et` (Python 3.12) | executorch 1.5.0, torch 2.14.1, torchao 0.18.0, onnx 1.23.2, onnx2torch 1.5.15, onnxruntime 1.31.0 |
| Board `~/et-venv` (Python 3.12) | executorch 1.5.0 (pip wheel), torch 2.14.1+cpu, torchao 0.18.0 |
| Board QAIRT | system `libqnn1`/`qairt-libs`/`qairt-dsp-binaries` 2.49.0 (`/usr/lib/libQnnHtp.so`, `/usr/lib/dsp/cdsp/libQnnHtpV75Skel.so`) |
| Board ExecuTorch source `~/git/executorch` | commit `5249a13c55`, patched (below), built with `EXECUTORCH_BUILD_QNN=ON`, `EXECUTORCH_BUILD_DEVTOOLS=ON` |

Board-side patches: the QCS8275 is not in ExecuTorch 1.5.0's chipset table, so `QcomChipset.QCS8275 = 82` (HtpArch V75) was added to `qc_schema.py`, `qc_compiler_spec.fbs` and `utils/utils.py`. A reference copy is in `demo/ventuno-pose/et/boardsrc/serialization/`. The QNN pybind adaptor (`PyQnnManagerAdaptor`) is built for aarch64; upstream builds it only for x86_64. The executor runner adds `--profile_level` and `--warm_up`.

Pipeline:

1. **ONNX → PyTorch:** the RTMPose-Body2d ONNX export from Qualcomm AI Hub is converted with `onnx2torch`.
2. **Make static:** `make_static.py` replaces data-dependent onnx2torch ops (Reshape/Squeeze/Split/GatherND with constant shape inputs) with static equivalents from `static_ops.py`. It checks a max output diff of 0 and that `torch.export` succeeds.
3. **`torch.export`** → `rtmpose_ep.pt2`, pushed to the board.
4. **Lower to QNN on the board** (ahead-of-time compilation runs on the aarch64 board because it has `libQnnHtpPrepare.so`):

   ```sh
   source ~/et-venv/bin/activate; cd ~/models/et
   QNN_SDK_ROOT=~/qairt-fake LD_LIBRARY_PATH=/usr/lib python export_qnn_onboard.py --soc QCS8275
   ```

   This calls `to_edge_transform_and_lower_to_qnn(..., generate_htp_compiler_spec(use_fp16=True))`, prints delegate/non-delegate op counts, and writes `rtmpose_qnn_fp16_QCS8275.pte` (38.8 MB).
5. **CPU variants (Mac):** `export_xnnpack.py` (fp32) and `export_xnnpack.py --int8` (PT2E, per-channel symmetric, calibrated on 20 real crops).

Run on the board:

```sh
export LD_LIBRARY_PATH=$HOME/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"
~/git/executorch/build-x86/examples/qualcomm/executor_runner/qnn_executor_runner \
  --model_path rtmpose_qnn_fp16_QCS8275.pte --input_list_path list.txt --output_folder_path out \
  --iteration 1 --warm_up 2 --profile_level 2 --etdump_path qnn_fp16.etdp
```

(`build-x86` is a misnamed aarch64 build directory on the board.)

## 3. Gemma 3 1B on the NPU (coaching-cue phrasing)

`web/processor/commentary.py` sends the measured evidence and an already-approved cue to `qnn_llama_runner` with the ExecuTorch QNN `gemma3-1b_qcs8275_ctxt-5000.pte` (1.17 GB, hybrid AR-128 prefill + KV decode). Measured on the board: load 2.6–2.9 s, prefill 33–37 tokens in 59–65 ms (508–627 tok/s), decode 30.3–30.8 tok/s, 1.31 GB RSS.

In an early test the model inverted a cue: it told a player who bent too little to straighten their legs. That is why **deterministic rules choose the fault and its direction, and the LLM only rephrases it.** A validator rejects replies that add measurements, unsupported body or action advice, or reverse the bend direction, and falls back to the template text.

## 4. Linux / MCU boundary

The VENTUNO Q has two compute domains:

- **Linux (QCS8275 application processor + Hexagon NPU):** camera capture, ExecuTorch pose inference, serve-event detection, comparison with the pro reference, rule selection, LLM phrasing and speech. All ML inference happens here.
- **STM32H5 MCU (Zephyr):** real-time physical I/O. It enumerates as `/dev/ttyACM0` and is reached from Linux through `arduino-router` (MsgPack-RPC; `arduino-router-cli` on the Linux side, the `Arduino_RouterBridge` library in the sketch).

The intended contract: the MCU owns the **record/complete button** (it raises `serve_done` to Linux) and the **result indicator** (Linux calls `show_result(code)` to drive an LED or buzzer). Linux never drives GPIO directly, and the MCU never runs inference.

> **Status:** the Bridge toolchain is installed and the MCU enumerates on the board. A Djoker sketch and the Linux-side RPC calls are **not yet implemented**. In the current software the completion trigger is the Enter key or a UI button (`Session.trigger` / **Stop & analyse**), and feedback is on screen or spoken.

## 5. Known limits

- The NPU path is fp16. **int8 has been measured only on XNNPACK (CPU)**; there is no QNN int8 `.pte` yet.
- Latency and agreement numbers come from 20 crops of one clip, plus a 230-frame run on three clips. No labeled keypoints were available, so the 230-frame run is an execution and visual sanity check, not an accuracy score.
- In the web app's live-camera mode, the continuous *tracking* preview that decides when a serve starts and ends runs on onnxruntime CPU on the host. The saved serve clip is then re-run through the ExecuTorch NPU path for analysis.
- `rtmpose_torch.pt` and `rtmpose_ep.pt2` were produced interactively. The commands in `et/README.md` reconstruct those steps rather than replay a committed script.
