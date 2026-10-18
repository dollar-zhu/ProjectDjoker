# Ventuno Q board status (end of day 1, 2026-10-17)

Board: Arduino Ventuno Q `QCVENTUNO015` (QCS8275, Hexagon HTP v75, 8 cores, 15 GB RAM, 23 GB free on `/`), Ubuntu 24.04 aarch64, kernel 6.8.0-1078-qcom, user `arduino`, Python 3.12.3. Access: `adb` over USB (serial `242692658`), `adb forward tcp:2222 tcp:22; ssh -p 2222 arduino@localhost` (see `ventuno-ssh.md`), Tailscale `100.74.60.29` / `team-ventuno` (tailnet `jednghk@`, tailscale 1.104.1). Rules: don't change passwords, reflash, delete `~/models`, or touch Wi-Fi/Tailscale config. `apt` needs `-o Acquire::ForceIPv4=true -o Acquire::Retries=5`.

Everything below was reconstructed from the surviving files in `demo/ventuno-pose/{et,proof}/` and re-verified on the board where stated; the session that produced them was lost.

## 1. ExecuTorch pose model: RTMPose-m on the HTP

Model: RTMPose-Body2d (COCO-WholeBody, 133 keypoints, SimCC heads) from the Qualcomm AI Hub ONNX export (`et/onnx/rtmpose_body2d.onnx`, AI Hub metadata `qairt 2.50.0`, `onnx_runtime 1.30.0`). Input `image` `1x3x256x192` float32 0..255 BGR (model normalises internally; see `posepipe.rtm_input`). Outputs `pred_x` `1x133x384`, `pred_y` `1x133x512` (SimCC logits at 2x crop resolution; keypoint = argmax/2).

### Toolchain versions

| where | what |
|---|---|
| Mac `demo/ventuno-pose/et/.venv-et` (py3.12.3) | executorch 1.5.0, torch 2.14.1, torchao 0.18.0, onnx 1.23.2, onnx2torch 1.5.15, onnxruntime 1.31.0, numpy 2.5.4 |
| Board `~/et-venv` (py3.12.3) | executorch 1.5.0 (pip wheel), torch 2.14.1+cpu, torchao 0.18.0 |
| Board QAIRT | `libqnn1`/`qairt-libs`/`qairt-dsp-binaries` 2.49.0-0ubuntu1~bpo24.04.2 (`/usr/lib/libQnnHtp.so`, `libQnnHtpPrepare.so` = `v2.49.0.260730134355`; skels in `/usr/lib/dsp/cdsp/libQnnHtpV75Skel.so`) |
| Board ExecuTorch source `~/git/executorch` | commit `5249a13c55` (2026-08-13, "Fix remaining CompileMode test regressions (#21801)"), with teammate patches (below) |

Teammate patches in `~/git/executorch` (uncommitted, `git diff --stat` = 14 files): `backends/qualcomm/CMakeLists.txt` builds the pybind adaptor on `aarch64` (upstream only `x86_64|AMD64`); `qc_schema.py`/`qc_compiler_spec.fbs`/`utils/utils.py` add `QcomChipset.QCS8275 = 82` (HtpArch V75, 8 cores) to the chipset tables; plus llama-runner and executor_runner changes (`--profile_level`, `--warm_up`) used below.

Two native builds on the board (both `RelWithDebInfo`, `/usr/bin/c++`):

- `~/git/executorch/build-x86/` (misnamed, it is an aarch64 build): `EXECUTORCH_BUILD_QNN=ON`, `EXECUTORCH_BUILD_DEVTOOLS=ON`, `QNN_SDK_ROOT=/home/arduino/derrjohn_local/qairt/2.46.0.260424/` at configure time (headers); runtime links against the system 2.49 libs. Produces `backends/qualcomm/libqnn_executorch_backend.so`, `backends/qualcomm/PyQnnManagerAdaptor.cpython-312-aarch64-linux-gnu.so`, `examples/qualcomm/executor_runner/qnn_executor_runner`, `examples/qualcomm/oss_scripts/llama/qnn_llama_runner`.
- `~/git/executorch/build-xnnpack/`: `EXECUTORCH_BUILD_XNNPACK=ON`, devtools off; produces `executor_runner`.

### How the QNN .pte was produced (AOT on the board itself)

The 1.5.0 pip wheel has no aarch64 `PyQnnManagerAdaptor`, so the teammate-built one was dropped into the wheel's package, together with the patched serialization files (the `.fbs` schema must match the adaptor; the copies live in `et/boardsrc/serialization/` for reference):

```sh
# board, once
cp ~/git/executorch/build-x86/backends/qualcomm/PyQnnManagerAdaptor.cpython-312-aarch64-linux-gnu.so ~/et-venv/lib/python3.12/site-packages/executorch/backends/qualcomm/python/
cp ~/git/executorch/backends/qualcomm/serialization/{qc_schema.py,qc_compiler_spec.fbs,qc_schema_serialize.py} ~/et-venv/lib/python3.12/site-packages/executorch/backends/qualcomm/serialization/
mkdir -p ~/qairt-fake/lib && ln -s /usr/lib ~/qairt-fake/lib/aarch64-ubuntu-gcc9.4   # QNN_SDK_ROOT layout the python side expects
```

Mac side (`.venv-et`, in `demo/ventuno-pose/et/`): ONNX -> torch via onnx2torch (`rtmpose_torch.pt`), then `python make_static.py` replaces the data-dependent onnx2torch ops (Reshape/Squeeze/Split/GatherND with constant shape inputs) by static equivalents recorded from one forward pass (`rtmpose_torch_static.pt`, max diff 0), `torch.export` -> `rtmpose_ep.pt2` (72.8 MB), pushed to `~/models/et/`.

Board side:

```sh
source ~/et-venv/bin/activate; cd ~/models/et
QNN_SDK_ROOT=~/qairt-fake LD_LIBRARY_PATH=/usr/lib python export_qnn_onboard.py --soc QCS8275        # --tiny for a 1-conv smoke model
```

`export_qnn_onboard.py` calls `to_edge_transform_and_lower_to_qnn(model, inputs, generate_qnn_executorch_compiler_spec(soc_model=QcomChipset.QCS8275, backend_options=generate_htp_compiler_spec(use_fp16=True)))`, prints delegate-call / non-delegated op counts, and writes `rtmpose_qnn_fp16_QCS8275.pte` (38.8 MB, i.e. fp16 weights). **This is fp16 on HTP, not int8**: no PT2E quantisation was done for the QNN path yet.

### How the XNNPACK .pte files were produced (Mac, `.venv-et`)

```sh
cd demo/ventuno-pose/et
.venv-et/bin/python export_xnnpack.py                                   # rtmpose_xnnpack_fp32.pte, 71.8 MB
.venv-et/bin/python export_xnnpack.py --int8 --out rtmpose_xnnpack_int8.pte   # 20.2 MB
```

fp32: `torch.export` -> `to_edge_transform_and_lower(partitioner=[XnnpackPartitioner()], EdgeCompileConfig(_check_ir_validity=False))`. int8: `XNNPACKQuantizer` with `get_symmetric_quantization_config(is_per_channel=True)`, `prepare_pt2e` calibrated on the 20 real crops in `et/calib/*.npy` (made by `proof/make_frames.py` from `nvidia_serve_overlay.mp4` using the MediaPipe detector ROI), `convert_pt2e`, then the same lowering.

### Running on the board

```sh
export LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"
cd ~/models/et    # frames/fNN.raw = 1x3x256x192 float32 LE (589,824 B), same 20 crops as proof/frames
# QNN / HTP (input list = one raw path per line; outputs out/output_<frame>_<k>.raw)
printf 'frames/f00.raw\n' > list1.txt
~/git/executorch/build-x86/examples/qualcomm/executor_runner/qnn_executor_runner --model_path rtmpose_qnn_fp16_QCS8275.pte --input_list_path list1.txt --output_folder_path out --iteration 1 --warm_up 2 [--profile_level 2 --etdump_path x.etdp]
# XNNPACK / CPU (outputs <output_file>-0.bin, -1.bin)
~/git/executorch/build-xnnpack/executor_runner --model_path rtmpose_xnnpack_int8.pte --inputs frames/f00.raw --num_executions 3 --cpu_threads 8 --output_file out/f00 --print_output none
```

Re-verified today: the QNN run on `frames/f00.raw` wrote `output_0_0.raw` (204,288 B = 133x384 float32) and `output_0_1.raw` (272,384 B = 133x512 float32), bit-identical to the saved `proof/out_qnn_fp16/` outputs (max abs diff 0.0, identical argmax). ETDump written to `etdump.etdp` (576 B at profile level 0).

### Measurements (`proof/bench.json`, `et/bench_board.py`; 20 crops, warm)

| run | backend | per-frame mean over 20 crops | hot loop (50 iters, 1 frame) | peak RSS (`/usr/bin/time -v`) | load |
|---|---|---|---|---|---|
| `rtmpose_qnn_fp16_QCS8275.pte` | QNN HTP fp16 | **6.45 ms** (6.3-6.7) | 4.49 ms | **50 MB** | method load 222 ms |
| `rtmpose_xnnpack_fp32.pte` | XNNPACK CPU, default threads | 198 ms (121-235) | 201 ms (p95 228) | 140 MB | 193 ms |
| same, `--cpu_threads 4` / `8` | | | 85.9 ms (p95 182) / 111 ms (p95 128) | | |
| `rtmpose_xnnpack_int8.pte` | XNNPACK CPU, default threads | 77 ms (69-85) | 80 ms (p95 90) | 41 MB | 79 ms |
| same, `--cpu_threads 4` / `8` | | | 37.9 ms (p95 61) / **27.9 ms** (p95 33) | | |

Default-thread XNNPACK numbers are from `--num_executions 3` single-frame runs and are noisy (other adb jobs were running); the `--cpu_threads` rows are the usable ones. HTP is 13-30x faster than the best CPU configuration at a third of the memory.

Agreement vs onnxruntime fp32 on the Mac (`proof/agreement.json`, `et/proof_report.py`; 17 COCO body joints, ORT conf >= 0.3, 193 joints over 20 crops, crop px = SimCC argmax/2, PCK threshold 0.05 x 256 = 12.8 px):

| run | mean px err | median | max | PCK@0.05 | mean abs conf diff |
|---|---|---|---|---|---|
| QNN fp16 | 0.24 | 0.0 | 1.12 | **1.000** | 0.006 |
| XNNPACK fp32 | 0.00 | 0.0 | 0.00 | 1.000 | 5e-7 |
| XNNPACK int8 | 1.22 | 0.71 | 13.5 | 0.995 | 0.020 |

Overlay sheet: `proof/overlay_qnn_vs_ort.png` (orange ORT, green HTP). Int8 is XNNPACK-only so far; its one 13.5 px outlier is a single joint on one crop.

### ETDump summary (`proof/qnn_fp16.etdp` -> `proof/qnn_fp16_etdump_ops.csv`, `--profile_level 2`, 20 frames x (1 iter + 2 warm-up) = 60 executions)

- Execute block: 302 rows; **300 delegated (QNN), 2 non-delegated**, and the two non-delegated rows are the wrappers `Method::execute` (6.55 ms avg) and `DELEGATE_CALL` (6.55 ms avg). **No operator fell back to the CPU: the whole graph is one QNN delegate.** (`export_qnn_onboard.py` prints the delegate-call / non-delegated op lists at export time; that console output was not preserved, the ETDump is the evidence.)
- Per-op HTP profile: 288 ops on the HTP, by type: mul 72, convolution 62, sigmoid 58 (SiLU = mul+sigmoid), view_copy 20, add 16, permute_copy 13, matmul 7 (SimCC heads / GAU attention), clamp 6, cat 5, div 4, mean_dim 4, pow 4, constant_pad_nd 3, max_pool2d 3, abs 2, sum 2, split 2, _to_copy/index/sub/unsqueeze/relu 1 each.
- HTP timers (avg per execution): QNN execute 6.14 ms, RPC execute 5.66 ms, accelerator execute 4.17 ms (4.13 ms excluding wait), 6.81 M accelerator cycles, 4 HVX threads, VTCM acquire 0.17 ms, HVX+HMX power-on 0.23 ms, 0 yields. Init: `Method::init` 219.7 ms (context binary load).
- Heaviest ops by cycles: `aten_sub_tensor:OpId_74` 14.8 % and `aten_div_tensor:OpId_75` 12.1 % (the model's built-in mean/std input normalisation on the full 256x192x3 input), one 1x1 convolution `OpId_742` 11.7 %, then elementwise muls 2-6 % each. Folding the normalisation into the first conv (or doing it on the CPU in uint8->fp16) would remove ~27 % of HTP cycles.

## 2. Clip transfer Mac -> board (20 MB random file, md5 verified)

| path | time | note |
|---|---|---|
| `adb push` | 0.25 s (81.6 MB/s) | fastest, USB only |
| `scp -P 2222` via `adb forward tcp:2222 tcp:22` | 2.44 s | USB only |
| HTTP multipart POST to `inbox_server.py` via `adb forward tcp:8001 tcp:8000` | 1.64 s server-side (1.67 s wall) | same path a phone would use |
| `scp arduino@100.74.60.29` (Tailscale) | **not measured** | the Mac's Tailscale.app is logged out (`Tailscale status` -> `Logged out. ... NeedsLogin`); the board's `tailscale status` lists only itself, so there is currently no peer on the tailnet. `ping 100.74.60.29` 100 % loss from the Mac. |

What was verified on the Tailscale side: on the board, `python3 -m http.server 8000 --bind 0.0.0.0` and `inbox_server.py` both answer `200` on `http://100.74.60.29:8000/` (curl from the board to its own tailnet address, 6 ms), so the server binds the tailnet interface; only the Mac-side login is missing. To finish: `open -a Tailscale` on the Mac, sign in with the same account (`jednghk@`), then `scp clip.mp4 arduino@100.74.60.29:~/inbox/` and `curl -F clip=@clip.mp4 http://team-ventuno:8000/upload`. The board's `~/ts-up.log` shows the login URL flow that was used for the board (`tailscale up` -> `https://login.tailscale.com/a/...` -> `Success.`); don't re-run it.

`demo/ventuno-pose/inbox_server.py` (new, stdlib only, copied to `~/inbox_server.py` on the board, currently running as PID 12420, log `~/inbox_server.log`): GET `/` = phone-friendly upload form (`<input type=file accept="video/*" capture=environment>`), POST `/upload` = multipart save to `~/inbox/<timestamp>_<name>` (returns JSON with bytes and seconds), GET `/files/` = directory listing. Phone -> board over Tailscale: install the Tailscale iOS/Android app, sign in to the same tailnet, then in the phone browser open `http://team-ventuno:8000/` (MagicDNS) or `http://100.74.60.29:8000/`, pick a clip, Upload. Venue Wi-Fi client isolation does not matter because the traffic goes through the Tailscale tunnel (DERP relay if direct UDP fails; expect a few MB/s, so a 20 MB clip is 5-20 s). Alternative without Tailscale: phone hotspot shared by board and Mac (`ventuno-ssh.md`).

## 3. Speech, LLM, MCU

### Piper TTS (CPU, onnxruntime)

`python3 -m venv ~/tts-venv && ~/tts-venv/bin/pip install piper-tts` -> piper-tts 1.8.0, onnxruntime 1.31.0 (CPU). Voice: `~/tts-venv/bin/python -m piper.download_voices en_US-lessac-medium` -> `~/models/piper/en_US-lessac-medium.onnx` (63 MB) + `.json`. (A teammate had already done the same in `~/piper-venv` / `~/piper-voices`; both work.)

```sh
echo "Toss the ball a little further in front of you and reach up to meet it." | ~/tts-venv/bin/piper -m ~/models/piper/en_US-lessac-medium.onnx -f out.wav
```

16-word sentence -> 3.39 s of 22,050 Hz audio in **3.25 s wall / 209 MB RSS** (3.28 s on a second run), including process start and model load, i.e. roughly real-time as a one-shot process. For the demo keep one piper process alive (or use the Python API `PiperVoice.load` once) so only synthesis time remains. Not ExecuTorch, not on the HTP; fine for the "phrasing" part of the loop, not a scoring item. Audio out: no speaker checked yet (a Logitech Brio 101 webcam is attached on USB bus 1 and has a mic; `lsusb`).

### Gemma 3 1B on the HTP (`qnn_llama_runner`, ExecuTorch QNN)

```sh
export LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"
cd ~/models/gemma3-1b_qcs8275_ctxt-5000
~/git/executorch/build-x86/examples/qualcomm/oss_scripts/llama/qnn_llama_runner --model_path gemma3-1b_qcs8275_ctxt-5000.pte --tokenizer_path tokenizer.json --decoder_model_version gemma3 --eval_mode 1 --seq_len 96 --temperature 0 --output_path out.txt --prompt "..."
```

`.pte` 1.17 GB (context length 5000, hybrid prefill AR-128 + kv decode). Two runs today: load 2.6-2.9 s; prefill 33-37 tokens in 59-65 ms (**508-627 tok/s**); decode **30.3-30.8 tok/s** (8 tokens 0.26 s; 58 tokens 1.88 s); time to first token 59-65 ms; RSS 1.31 GB. Output for "Rewrite as one short coaching cue, external focus, no jargon: the player bends the knees too little before the jump." was "Focus on straightening your legs before jumping." (wrong direction: the cue should ask for more bend), which supports the team design of deterministic rules choosing the fault and the LLM only phrasing, with a template fallback. The `re2 DFA out of memory` lines at start are tokenizer warnings and harmless. Full per-run stats land in `--performance_output_path`.

### Arduino Bridge / STM32H5

- The MCU enumerates on the board as USB `1209:ca01 Generic Arduino Generic board` -> `/dev/ttyACM0` (group `dialout`); `/dev/ttyMSM0` is the SoC UART. `arduino-cli board list` shows `/dev/ttyACM0 serial` (board name Unknown with the installed core).
- Installed packages: `arduino-cli 1.5.1` (`/usr/bin/arduino-cli`, core `arduino:zephyr 0.90.0` installed, 1.0.0 available), `arduino-app-cli 0.12.1` (daemon on `127.0.0.1:8800`, `arduino-app-cli monitor` attaches to the MCU serial), `arduino-app-lab 0.9.0`, `arduino-router 0.9.0` (`arduino-router.service` + `arduino-router-serial.service` active; `arduino-router-cli <METHOD> [args]` sends MsgPack-RPC requests/notifications to the MCU, this is the "Bridge"), `arduino-ventunoq 0.2.0`, `arduino-ventunoq-config 0.3.0`, `/opt/openocd`. Sketch-side libraries already in `~/Arduino/libraries`: `Arduino_RouterBridge`, `Arduino_RPClite`, `MsgPack`, `ArxContainer`, `ArxTypeTraits`, `DebugLog`.
- `arduino-app-cli brick list` includes `arduino:tts`, `arduino:llm`, `arduino:asr`, `arduino:keyword_spotting`, `arduino:object_detection`; `arduino-app-cli model list` has built-in QNN models (face detection, YoloX, ...) but no pose model.
- No `pip` package for the bridge (none in system pip, `~/et-venv`, `~/tts-venv`); the Linux side talks to the MCU through `arduino-router` (MsgPack-RPC over `/dev/ttyACM0`), so an MCU feature (LED ring / buzzer / button to start recording) means a Zephyr sketch using `Arduino_RouterBridge` flashed via `arduino-cli`/`arduino-app-cli`, and `arduino-router-cli` notifications from Python. Not tested today; the full ttyACM0 line is shared with the router, so don't open it directly while the service runs.

## 4. Day-2 recommendation

Scoring is ExecuTorch integration 25 + on-device efficiency 15, so lead with what already works and make it end-to-end:

1. **Replace `qnn-net-run` in `posepipe.py` with the ExecuTorch runner** (`qnn_executor_runner --input_list_path` over the clip's crops; ~6.5 ms/frame + 0.22 s load). Keep the MediaPipe detector for the ROI for now or swap in the first frame's RTMPose box; this makes the demo "ExecuTorch runtime + QNN backend on QCS8275" rather than a context-binary bypass. Budget 2 h.
2. **Quantise RTMPose for the HTP** (the honest gap: HTP is fp16, int8 exists only on XNNPACK): `QnnQuantizer` + `prepare_pt2e`/`convert_pt2e` with the 20 `calib/*.npy` crops in `export_qnn_onboard.py`, re-run `bench_board.py qnn_int8` + `proof_report.py`, and add the row to the tables above. Also try folding the mean/std normalisation into the first conv (27 % of HTP cycles). Budget 2-3 h; if it fails, say so in the slide and keep fp16 (PCK 1.0).
3. **Clip path**: sign the Mac (and one phone) into Tailscale, re-measure the Tailscale rows, leave `inbox_server.py` running under a `systemd --user` unit so the phone upload form is always up; a watcher on `~/inbox` triggers the pipeline. Budget 1 h.
4. **Coaching loop**: deterministic fault picker on the 2D angles -> one cue -> gemma3 for phrasing (30 tok/s, so a 25-token cue is ~1 s after a 2.7 s load; keep the runner resident or accept the load) -> piper to wav -> play on the board or return to the phone via `/files/`. Prompt the LLM with the exact direction of the fix and a template fallback, given today's inverted cue. Budget 3 h.
5. Optional, only if 1-4 are done: MCU cue (LED colour / buzzer on fault) through `arduino-router-cli` for the "Bridge" story.

Known limits to repeat in the writeup: 2D RTMPose from a phone vs 3D H36M reference (no joint-for-joint comparison without mapping + projection), heuristic phase events, benchmark numbers from 20 crops of one clip, int8 PCK measured on XNNPACK only.
