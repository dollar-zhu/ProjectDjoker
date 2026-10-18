# On-device tennis serve coach: 2-day build plan

Status: DRAFT, 17 Oct 2026 15:15. Sections marked `[PENDING: agent]` are filled in when the
research agents report (`docs/board-status.md`, `docs/research/coach-checkpoints.md`,
`benchmark/clips.csv`).

Team: 2 people. Track A = board / pipeline (engineer). Track B = rules / UX / benchmark / pitch.
Day 1 = today from 15:30. Day 2 = Sat 18 Oct.

One-line pitch: **A serve coach in your bag that never uploads your video.** Film a serve on
your phone, the board watches it on the NPU, and you get one fix at a time.

---

## 0. Success criteria (what "done" means)

Must-have (demo works):
1. One phone clip (side or rear, player fills the frame, full body + toss peak visible) reaches
   the board and is processed end-to-end with no Mac in the loop.
2. Pose runs through the **ExecuTorch runtime** (`.pte`; QNN/HTP preferred, XNNPACK fallback).
   ETDump shows which ops ran where. Warm time per clip (≈60 frames) under 2 s on HTP, under
   10 s on XNNPACK.
3. Events (contact, toss apex, deepest knee bend, landing) within ±3 frames of hand-marked
   frames on ≥80 % of the dev clips.
4. Per clip: ONE root fault, the player's frozen key frame beside a pro's with a ghost
   skeleton, one external-focus cue, one drill; spoken in <10 s and shown on screen.
5. Low-confidence state ("can't judge from this angle") fires instead of guessing.

Should-have (credible):
6. On ≥15 held-out coach-labelled amateur clips, top-1 fault agreement beats baseline 1
   ("always say the most common fault"). If not, the slide says so.
7. ≥4 checkpoints each for side and rear that are genuinely visible from that angle, with
   cited thresholds.

Inspectable by the team: every processed clip writes a folder (section 7.1) and an HTML index
lists all clips with their verdicts so wrong calls are easy to spot.

---

## 1. Raw inputs to collect

### 1.1 Phone capture protocol

| Item | Side view (primary) | Rear view |
|---|---|---|
| Position | On the baseline extension, hitting-arm side, so the server is in profile at contact | Directly behind the server, 1–1.5 m toward the centre mark so the toss arm does not occlude the racket arm |
| Distance | 5–6 m. Player height ≈ 50–60 % of frame height **with the toss peak still in frame** (≈ 1 m above fingertip reach ≈ 3.3 m above ground) | 5–6 m, same framing rule |
| Camera height | Hip height (~1.0 m), tripod, level | Chest height (~1.3 m), level |
| Orientation | **Portrait** (toss peak needs vertical room) | Portrait |
| Frame rate | 120 fps slow-motion if the phone has it, else 60 fps. 30 fps is accepted but contact-frame error doubles | same |
| Resolution | 1080p is enough; 4K wastes transfer time | same |
| Audio | On. Contact detection uses the audio onset; wind and conversation degrade it | same |
| Clip length | 6–8 s per serve: start before the first ball bounce, stop after landing. One serve per clip | same |
| Exposure | Lock exposure/focus before the set; backlit (sun behind player) clips go to low-confidence | same |
| Ball | Yellow/optic ball, no yellow clothing or yellow court lines in frame near the toss path (HSV filter) | same |

Framing check (done by the first detected pose): all 17 keypoints with confidence >0.3 in the
first second; estimated toss-peak height (wrist-y at setup minus 1.6 × torso length) inside the
frame; player bounding-box height between 35 % and 75 % of frame height. Otherwise: "Move the
phone back a step and tilt it up" / "Move the phone closer."

### 1.2 Benchmark clip list schema

`benchmark/clips.csv` (one row per clip; URLs + timestamps + labels only, no video stored):

```
id,source_type(a/b/c),channel_or_subreddit,url,start_s,end_s,
camera_angle(side/rear/front/other),player_fills_frame,full_body_visible,toss_peak_visible,
fps_estimate,slow_motion,handedness,serve_type(flat/kick/slice/unknown),
level_estimate(beginner/intermediate/advanced),
coach_fault_1,coach_faults_other,coach_cue,coach_drill,label_confidence(high/low/none),
licence_note,notes
```

Companion files: `benchmark/labels_<initials>.csv` (blind labels per team member, same id),
`benchmark/heldout_ids.txt` (frozen before any threshold tuning), `benchmark/events_marked.csv`
(hand-marked contact/toss-apex/landing frames for a 10-clip subset).

`[PENDING: benchmark-scout]` candidate list, held-out split, most-common-fault baseline, pro
reference clips.

---

## 2. Hour-by-hour plan

`[PENDING: ventuno-engineer]` the fallback outcome decides the shape of day 1 evening. Skeleton:

### Day 1 (Fri 17 Oct, 15:30 →)

| Time | Track A (board) | Track B (rules/UX/benchmark) |
|---|---|---|
| 15:30–17:30 | Agent runs the `.pte` ladder (QNN → XNNPACK). Human: read agent checkpoints, unblock SDK downloads/accounts | Review coach checkpoint table; pick the 6–8 we implement; write `rules/checkpoints.yaml` (metric, band, cue, drill, angles) |
| 17:30 | **RISK GATE 1 (hour 2 of actual work).** A pose `.pte` runs on the board? Yes → continue A. No → one more rung only; by 19:30 (hour 4) we commit to whatever runs | Freeze held-out ids (every 3rd row). Start blind labelling of the remaining dev rows |
| 17:30–19:30 | Port `posepipe.py` to run **on the board**: ffmpeg frame extraction → person crop → `.pte` inference → `keypoints.json`. Keep the Mac-driven path as a debug tool | `events.py`: audio onset (librosa), yellow-ball HSV + apex, deepest knee bend (min included angle), landing (front ankle y) on the existing demo stills/clip |
| 19:30 | **RISK GATE 2 (hour 4).** Final backend decision. Write it into README | Shoot our own 10 test serves if anyone can reach a wall/garage (no court needed for toss + trophy) |
| 19:30–22:00 | ETDump + latency + memory proof script; clip transfer path (hotspot / adb reverse); Piper install | `rules.py`: checkpoint evaluation + priority tree + abstention; unit tests on synthetic keypoints |
| 22:00 | Sync: run one real clip end-to-end on the board, even if ugly | Write between-sets screen (static HTML, one file) |

### Day 2 (Sat 18 Oct)

| Time | Track A | Track B |
|---|---|---|
| 09:00–11:00 | FastAPI on board: `POST /clip` → folder; serve the inspection HTML | Run dev clips through the pipeline; tune bands on dev set only; log every change |
| 11:00–12:30 | Side-by-side key-frame renderer (player frame + pro frame + ghost skeleton) | Score held-out set; compute metrics table; write the "what would prove us wrong" line |
| 12:30–14:00 | MCU traffic light via Bridge (cut first if behind) | Report-card screen + low-confidence screen |
| 14:00–15:30 | Record demo clips (pre-recorded path) and one live capture rehearsal | README/docs: architecture, model card, proof tables, limitations |
| 15:30–17:00 | Freeze. Only bug fixes | Slides: pitch, loop diagram, proof numbers, benchmark result, honest limits |
| 17:00 | Full demo rehearsal ×2, timed | |

Fallback consequences:
- QNN `.pte` fails → XNNPACK `.pte` (lose ~10 pts of the efficiency story; keep ExecuTorch).
- Both fail → QNN context binary (lose most of the 25 ExecuTorch pts; say so plainly; show the
  `.pte` attempt and error in docs for partial credit).
- Phone → board Wi-Fi fails at venue → phone → Mac (AirDrop) → `adb push`; the Mac is a dumb
  cable, all compute stays on the board; say so in the demo.
- Audio contact detection fails → fall back to wrist-speed peak; mark confidence `low`.
- Toss ball not found → fall back to toss-wrist release point + apex of toss-hand trajectory;
  cannot judge toss placement; abstain on toss checkpoints.

---

## 3. Checkpoint rule table

`[PENDING: coach-researcher]` populated from `docs/research/coach-checkpoints.md`. Each row
carries: stage, metric on COCO-17 + events, pro band + fault threshold + source, cue, drill,
pass rule, visible-from-side, visible-from-rear.

Engineering conventions for every metric:
- Normalise lengths by hip width (rear) or torso length (side) measured at the setup frame.
- Angles are 2D included angles in image plane; state the projection assumption.
- Each metric has `value, band_lo, band_hi, confidence` where confidence = min keypoint
  confidence of the joints used × angle-suitability (1.0 for the metric's preferred view, 0.5
  for "partly", 0 for "no").
- A checkpoint is `fail` only if `confidence ≥ 0.5` and value outside the band; otherwise
  `unknown`. `unknown` never produces a cue.

---

## 4. Fault-priority tree

`[PENDING: coach-researcher]` reasoning and exceptions. Implementation:

```
faults = [c for c in checkpoints if c.status == 'fail']
if not faults and any(c.status == 'unknown' for c in critical): -> LOW_CONFIDENCE screen
root = min(faults, key=lambda c: STAGE_ORDER[c.stage])      # setup<toss<trophy<leg<contact<landing
```
Baseline rule: a fault counts only if present in ≥6 of 10 baseline serves (demo: ≥3 of 5).
Ties inside a stage are broken by effect size (distance outside band / band width).

---

## 5. Benchmark: build steps, scoring, targets

### 5.1 Build
1. Take `benchmark/clips.csv` from the scout. Drop `front/other`. Freeze `heldout_ids.txt`
   (every 3rd id, ≥15 rows) **before** any pipeline run. Commit it.
2. Two team members blind-label the dev rows with the checklist from §3; record in
   `labels_<initials>.csv`; compute Cohen's kappa (`sklearn.metrics.cohen_kappa_score`).
   Faults with disagreement are excluded and listed as "not reliably detectable".
3. Where a coach label exists it overrides ours.
4. Local processing only: `yt-dlp` to a temp dir, run pipeline, keep only outputs, delete video.
5. Hand-mark contact / toss apex / landing frames on 10 dev clips (`events_marked.csv`).

### 5.2 Scoring script spec (`benchmark/score.py`)
Inputs: `clips.csv`, `heldout_ids.txt`, per-clip `out/<id>/verdict.json`
(`{root_fault, top3, abstained, reason, events, checkpoints}`), optional `events_marked.csv`.
Outputs `benchmark/results.md` + `results.json`:
- top-1 agreement, top-3 recall (overall, by angle, by confidence)
- priority agreement: when label lists several faults, did we pick the earliest stage?
- abstention: correct abstentions / (clips whose label is in the cannot-see list or angle
  unsuitable); false confident claims counted separately
- cue rubric (0–4: right fault, external focus, actionable, drill from a cited source) — manual
  column in a CSV, aggregated by the script
- pipeline: pose success rate (≥15 keypoints >0.3 on ≥90 % of frames), event detection rate,
  contact-frame MAE vs hand marks
- baselines: (1) always most-common fault; (2) VLM shown 3 key frames, no rules (gemma3 on board
  or a Mac-side model; mark which)

### 5.3 Targets for the slide and the kill line
- Top-1 agreement ≥ 50 % on held-out side-view clips (baseline 1 expected ≈ 30–35 %).
- Abstention precision ≥ 80 % (when we say "can't see", we're right).
- Contact-frame MAE ≤ 2 frames at 60 fps.
- Pose success ≥ 90 % of side/rear clips with player filling the frame.
- **We are wrong if** top-1 agreement on held-out is not above baseline 1 by ≥ 10 points, or
  abstention precision < 60 %. Then the slide says: "the rules don't beat a prior yet; here is
  the per-clip inspection page showing why."

---

## 6. UX spec

Rules: one message at a time; no joint angles to the player; large tap targets; black on
white/yellow, high contrast; speech ≤ 10 s; the board (not the phone) decides what to say.

### 6.1 Channels per loop step

| Step | Channel | Exact wording |
|---|---|---|
| 0 Setup | Phone screen + voice | "Right- or left-handed?" [Right][Left] · "Which serve? Flat is the default." [Flat][Slice][Kick] · "Which grip do you use?" [Continental][Eastern][Not sure] (stored; never inferred) · Framing check: "Serve once so I can check the camera." → "Good, I can see your whole body and the toss." or "Move the phone back a step and tilt it up." |
| 1 Baseline | Light: amber steady. Voice only at start/end | "Ten serves, no feedback. Go." … "Done. Give me a second." |
| 2 Diagnose | Phone screen (between-sets layout) + voice once | "One thing to work on: your toss drifts behind you, so you hit cramped and into the net. Here's you next to a pro at the same moment." |
| 3 Prescribe | Phone screen + voice | Cue: "Toss to the 1 o'clock spot on the ceiling." Drill: "Toss and catch, five times. I'll tell you when the toss is in the zone." |
| 4 Practice | Light per serve: green (in band) / red (out) / amber (can't judge). Voice only when out of band, ≤ 1 sentence: "Toss a little further forward." After 2 sets: voice summary every 5 serves: "3 of 5 in the zone." | |
| 5 Gate | Voice + light green blink ×3 | "Four of five. Toss is fixed for now; let's hit five full serves." → "That held up. Next: …" |
| 6 Retention + report | Phone screen (report card) | "Ten serves, no feedback." → report |
| Low confidence | Light amber blink; voice | "I can't judge that from this angle. Move the phone to the side of the court." |

### 6.2 Wireframes (phone portrait, 5-second readability)

Between sets:
```
┌──────────────────────────────┐
│ FIX #1 of 1                  │
│ TOSS DRIFTS BEHIND YOU       │  ← 28 pt, 1 line
├──────────────┬───────────────┤
│   YOU        │    PRO        │
│  [frozen     │  [pro frame   │
│   trophy     │   same        │
│   frame +    │   moment]     │
│   ghost      │               │
│   skeleton]  │               │
├──────────────┴───────────────┤
│ Why: contact gets cramped,   │
│ ball goes into the net.      │
│                              │
│ CUE  "Toss to 1 o'clock"     │  ← 24 pt
│ DRILL Toss & catch ×5        │
│                              │
│ Progress  ● ● ● ○ ○  3/5     │  ← gate 4 of 5
│                              │
│ [     ▶  NEXT 5 SERVES     ] │  ← 64 px tall
│ [ Show me the drill video  ] │
└──────────────────────────────┘
```

Report card:
```
┌──────────────────────────────┐
│ SESSION REPORT  · 42 serves  │
├──────────────────────────────┤
│ Fixed      ✔ Toss placement  │
│            in zone 2/10→8/10 │
│ Working on  Trophy: elbow    │
│            4/5 last set      │
│ Watch list  Knee bend        │
│            (not started)     │
├──────────────────────────────┤
│ Baseline vs now  [two-bar]   │
│ Retention (no feedback) 7/10 │
├──────────────────────────────┤
│ Next time: 5 toss-and-catch, │
│ then full serves.            │
│ Couldn't see: grip, spin.    │
│ [ Share report ] [ Done ]    │
└──────────────────────────────┘
```

Low confidence:
```
┌──────────────────────────────┐
│ ⚠  CAN'T JUDGE THIS ONE      │
│                              │
│ Reason: the toss is out of   │
│ frame / you're facing the    │
│ camera.                      │
│                              │
│ [diagram: phone at side of   │
│  court, 5 m, hip height]     │
│                              │
│ [    Re-check framing      ] │
│ [    Skip this serve       ] │
└──────────────────────────────┘
```

Judge screen (laptop, mirrors the board's HTML): left = live clip with skeleton overlay;
right = events timeline (toss apex · trophy · contact · landing ticks), checkpoint table with
pass/fail/unknown, ETDump summary (ops on HTP vs CPU, ms/frame), and the spoken sentence.

---

## 7. Pipeline, inspection output, demo script, docs

### 7.1 Per-clip inspection folder (`out/<clip_id>/`)
```
clip.mp4            copy or symlink of input (benchmark: deleted after run)
meta.json           angle, fps, handedness, serve type, framing check result
keypoints.json      per frame: 17×(x,y,conf), crop box, model id, backend
events.json         contact, toss_apex, deepest_knee, trophy, landing: frame + confidence + method
checkpoints.csv     checkpoint, stage, value, band_lo, band_hi, confidence, status(pass/fail/unknown)
verdict.json        root_fault, top3, abstained, reason, cue, drill, spoken_text
keyframes.png       player trophy/contact/landing beside pro frames, ghost skeleton
timeline.png        angles + wrist height + audio envelope with event ticks
etdump.txt          op table by delegate, latency mean/p95, RSS
feedback.wav        Piper output
```
`out/index.html`: one row per clip (thumbnail, angle, verdict, label, agree?, confidence,
link). This is the page the team inspects and the page judges see.

### 7.2 Pipeline stages (all on the board)
1. `ingest`: receive clip (FastAPI `POST /clip` or watched folder), ffprobe fps/rotation,
   ffmpeg → frames at native fps (cap 120) + mono 16 kHz wav.
2. `detect`: person box from first frames (MediaPipe detector already on board, or largest
   RTMPose response); fixed crop for the clip, 1.3× body height so feet and toss hand stay in.
3. `pose`: ExecuTorch runtime, `.pte` per frame on the crop → 17 keypoints. ETDump on demand.
4. `events`: audio onset (librosa `onset_strength` peak in the window after toss apex); ball
   HSV mask → apex (max height) and position; deepest knee bend (min included angle, smoothed);
   trophy (frame of toss apex, fallback highest hitting elbow before drop); landing (front
   ankle y stops decreasing after contact).
5. `rules`: evaluate checkpoints (§3) → status; priority tree (§4) → verdict / abstain.
6. `phrase`: template first; gemma3-1b (already on board) rewrites the cue sentence only, with
   a 20-token cap and a fallback to the template if it mentions a body part or exceeds length.
7. `speak`: Piper → wav → phone/HTML audio element. MCU light via Bridge.
8. `render`: keyframes.png, timeline.png, index.html.

### 7.3 Three-minute demo script
- 0:00 Hook (15 s): "Every serve-analysis app uploads your video. Ours never leaves this
  board." Hold up the Ventuno Q.
- 0:15 Live capture (45 s): teammate serves a toss-and-trophy (no ball strike needed — a wall or
  the stage is fine) filmed on the phone from the side; clip sent to the board; judge screen
  shows frames → skeleton → events → verdict in real time. Light goes amber → red.
- 1:00 Pre-recorded baseline (40 s): five amateur serves from the benchmark; screen shows the
  one fault chosen, player frozen beside pro, cue spoken by the board.
- 1:40 Practice set (30 s): five more serves, traffic light per serve, "4 of 5", gate passes.
- 2:10 Proof (30 s): ETDump table — ops on HTP, ms/frame, memory; int8 vs fp32 keypoint
  agreement; held-out benchmark result incl. baseline and the honest kill line.
- 2:40 Close (20 s): what it can't see (grip, pronation, racket face), Phase 2 on-court test,
  one-line pitch again.

### 7.4 README / docs sections (deployment + docs 10 pts)
1. What it does and what it refuses to claim (cannot-see list).
2. Hardware + software versions (board, QAIRT, ExecuTorch commit, model source + licence).
3. Reproduce: export `.pte` (script + exact command), push, run one clip, open index.html.
4. Proof: ETDump table, latency, memory, quantisation agreement.
5. Coaching rules: table with sources.
6. Benchmark: protocol, held-out freeze commit hash, results, kill line.
7. Capture protocol (§1.1).
8. Limitations and Phase 2 logging schema (`session.jsonl`: serve_id, timestamp, feedback_given,
   fault, in_band, outcome_in/out/zone/speed nullable) so court testing needs no code change.

---

## 8. Assumptions and claims the camera cannot support

Assumptions (flag on the slide):
- A single fixed crop per clip is enough (player stays roughly in place during a serve).
- Audio onset = ball contact (fails with wind, nearby courts, muted phones).
- Yellow HSV mask finds the ball (fails with yellow lines/clothes, strong backlight).
- 2D side-view angles approximate sagittal-plane angles (fails if the camera is >20° off axis).
- Djokovic 3D numbers are cross-checks only; joint layout provisional (H36M).
- Pro reference frames come from public clips with a different camera; the ghost overlay is a
  normalised pose, not a pixel-true comparison.

Not supported by body pose (always abstain): grip, forearm pronation, racket-face angle,
internal shoulder rotation, wrist snap, muscle tension/"stiffness", ball spin, racket drop
depth, ball speed, ball outcome (in/out) unless logged manually.
