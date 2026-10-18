"""Step-C proof driver: runs the QNN(HTP) and XNNPACK(CPU) RTMPose .pte files on the Ventuno Q over adb, collects
latency (warm, 50 iterations), peak RSS (/usr/bin/time -v, VmHWM), an ETDump for the QNN run, and the 20-frame
outputs for keypoint agreement vs onnxruntime (computed in proof_report.py). Writes ../proof/*.json and raw outputs."""
import subprocess, json, os, re, glob, sys, numpy as np
B = "/home/arduino/models/et"; RUN = "/home/arduino/git/executorch/build-x86/examples/qualcomm/executor_runner/qnn_executor_runner"
XR = "/home/arduino/git/executorch/build-xnnpack/executor_runner"
ENV = 'export LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib";'
def sh(c): r = subprocess.run(["adb", "shell", ENV + c], capture_output=True, text=True); return r.stdout + r.stderr
def rss(out): m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", out); return int(m.group(1)) / 1024 if m else None
os.makedirs("../proof", exist_ok=True)
frames = sorted(os.path.basename(f) for f in glob.glob("../proof/frames/f*.raw")); n = len(frames)
# ---- QNN / HTP ----
import sys; only = sys.argv[1:]
res = json.load(open("../proof/bench.json")) if os.path.exists("../proof/bench.json") else {}
for pte, tag in [("rtmpose_qnn_fp16_QCS8275.pte", "qnn_fp16")]:
    if only and tag not in only: continue
    sh(f"cd {B}; rm -rf out_{tag}; mkdir -p out_{tag}; printf '%s\\n' {' '.join('frames/' + f for f in frames)} > list_{tag}.txt")
    o = sh(f"cd {B}; /usr/bin/time -v {RUN} --model_path {pte} --input_list_path list_{tag}.txt --output_folder_path out_{tag} --iteration 1 --warm_up 2 --profile_level 2 --etdump_path {tag}.etdp 2>&1")
    per = [float(x) for x in re.findall(r"1 inference took ([\d.]+) ms", o)]; lines = [l for l in o.splitlines() if "Total" in l and "inference" in l]
    o50 = sh(f"cd {B}; printf 'frames/{frames[0]}\\n' > list1.txt; {RUN} --model_path {pte} --input_list_path list1.txt --output_folder_path out_{tag} --iteration 50 --warm_up 5 2>&1 | grep 'inference took'")
    res[tag] = {"pte": pte, "runner": RUN, "frames": n, "per_frame_ms_20": per, "total_line": lines, "peak_rss_mb": rss(o), "iter50_line": o50.strip(), "load_lines": [l for l in o.splitlines() if "loaded" in l.lower() or "Loading" in l][:4]}
    subprocess.run(f"rm -rf ../proof/out_{tag}; adb pull {B}/out_{tag} ../proof/out_{tag} >/dev/null; adb pull {B}/{tag}.etdp ../proof/{tag}.etdp >/dev/null", shell=True)
    print(tag, "per-frame ms:", np.round(per, 2).tolist(), "| rss MB", res[tag]["peak_rss_mb"], "|", o50.strip().splitlines()[:1])
# ---- XNNPACK / CPU ----
for pte, tag in [("rtmpose_xnnpack_fp32.pte", "xnnpack_fp32"), ("rtmpose_xnnpack_int8.pte", "xnnpack_int8")]:
    if only and tag not in only: continue
    if "No such file" in sh(f"ls {B}/{pte}"): print("skip", pte); continue
    sh(f"cd {B}; rm -rf out_{tag}; mkdir -p out_{tag}"); per = []
    for f in frames:
        o = sh(f"cd {B}; {XR} --model_path {pte} --inputs frames/{f} --num_executions 3 --output_file out_{tag}/{f[:-4]} --print_output none 2>&1 | grep 'Iteration 3'")
        m = re.search(r"Iteration 3 of 3: ([\d.]+) ms", o); per.append(float(m.group(1)) if m else None)
    o50 = sh(f"cd {B}; /usr/bin/time -v {XR} --model_path {pte} --inputs frames/{frames[0]} --num_executions 55 --print_output none 2>&1")
    its = [float(x) for x in re.findall(r"Iteration \d+ of 55: ([\d.]+) ms", o50)][5:]
    for thr in (4, 8):
        oth = sh(f"cd {B}; {XR} --model_path {pte} --cpu_threads {thr} --inputs frames/{frames[0]} --num_executions 25 --print_output none 2>&1"); it = [float(x) for x in re.findall(r"Iteration \d+ of 25: ([\d.]+) ms", oth)][5:]
        res.setdefault(tag + "_threads", {})[thr] = {"mean_ms": float(np.mean(it)), "p95_ms": float(np.percentile(it, 95))}
    res[tag] = {"pte": pte, "runner": XR, "frames": n, "per_frame_ms_20": per, "iter50_mean_ms": float(np.mean(its)), "iter50_p95_ms": float(np.percentile(its, 95)), "iter50_min_ms": float(np.min(its)), "peak_rss_mb": rss(o50), "load_line": [l for l in o50.splitlines() if "Model loaded" in l][:1]}
    subprocess.run(f"rm -rf ../proof/out_{tag}; adb pull {B}/out_{tag} ../proof/out_{tag} >/dev/null", shell=True)
    print(tag, "mean", res[tag]["iter50_mean_ms"], "p95", res[tag]["iter50_p95_ms"], "rss MB", res[tag]["peak_rss_mb"], res[tag + "_threads"])
json.dump(res, open("../proof/bench.json", "w"), indent=1); print("wrote ../proof/bench.json")
