# Serve playback and feedback implementation plan

17 October 2026. Next implementation plan following the manual video review and Ventuno RTMPose smoke test. This refines the original serve-coach draft around the evidence currently available.

## Outcome

A phone-friendly page where someone uploads one serve, watches it with an optional skeleton overlay, clicks labelled moments, and receives one supported coaching observation with a cue and drill. If the recording cannot support an observation, explain what recording is needed.

First milestone: the three saved usable clips work through playback, estimated events and a narrow feedback check. Second milestone: a fresh phone recording completes the same flow with processing on the Ventuno.

## Starting point

- Work in `ProjectDjoker`; the similarly named `djoker` chat directory is empty.
- Five local samples and source-time mappings live in `benchmark/manual/samples/`. Federer, Bremen and Sara are analysis candidates. Stephen and Vishal test unsuitable-input handling.
- RTMPose ExecuTorch QNN FP16 has processed 230 sampled frames on the Ventuno. Mac-side decoding, manually selected crops and rendering were used. This establishes execution, not coaching accuracy or automatic player tracking.
- `demo/ventuno-pose/inbox_server.py` is a minimal upload prototype, not an upload-to-analysis service.
- The existing `visualization/` page describes the Djokovic reference dataset; add the serve-review interface separately.
- These excerpts have no audio and include edited/slow-motion footage. Their playback times cannot establish real movement speeds. The Federer excerpt has no landing.

## Implementation order

### 1. Define results and manually label the clips

Create `benchmark/manual/events_marked.json` by inspecting original sample frames. For each event store clip id, event type, frame index, clip playback time, original source time, reviewer, visibility status, uncertainty interval and a short evidence note. Mark missing or ambiguous events explicitly.

Start with loading/deepest knee bend, upward reach and landing/recovery. Treat trophy position as a visible posture interval requiring review, not a synonym for toss apex. Label release/apex/contact only if the ball/racket evidence supports them. Manual labels are references and must remain separate from automatic predictions.

Define a shared result format:

- `meta.json`: clip duration, dimensions, presentation timestamps, rotation, handedness/view when known, crop selection and model version.
- `keypoints.json`: timestamp, player crop, 17 body joints and scores per sampled frame.
- `events.json`: event, estimated timestamp or interval, evidence frames, method, quality status, and unavailable reason where applicable.
- `feedback.json`: observation, linked event/interval, supporting measurements, cue, drill and evidence status. Distinguish automatic observations, manual annotations and attributed coach comments.
- `job.json`: queued/processing/complete/failed, current stage and useful error details.

Completion check: every sample has either reviewed marks or an explicit unsuitable-input record. Source offsets round-trip correctly; missing landing stays missing. Do not invent a confidence probability from uncalibrated joint scores.

### 2. Build the review page using saved results

Implement under `app/`, using a small Python HTTP API and plain HTML/CSS/JavaScript with native video and a canvas skeleton overlay. Reuse the wireframe's large player view, reference panel and single feedback card. Keep the first page usable on a phone and desktop without adding a frontend build system.

Include sample selection, play/pause, scrub, playback speed, skeleton toggle and clickable event markers. A selected marker seeks to the supporting moment and highlights its evidence interval. Show source/reference video beside the player only when a reviewed comparable moment is available; the comparison is illustrative, not a universal target.

Manual fixture markers must be visibly labelled as reviewed annotations until automatic predictions are connected. Empty feedback, processing, failed processing and cannot-judge states are first-class screens. Keep latency/debug details in an expandable inspection panel.

Completion check: all five samples load, seeking keeps the skeleton aligned, toggling it preserves playback position, the page works at phone width, and unsupported inputs display the correct limitation. Inspect actual browser playback rather than relying only on a screenshot or DOM test.

### 3. Estimate events from the pose sequence

Implement `analysis/events.py` with timestamp-aware smoothing, score/visibility gating and ordered candidate search. Begin with deepest visible knee bend, subsequent upward reach, and a landing candidate only when post-swing footage supports it. Preserve unknown states for ambiguity, occlusion and discontinuities. Do not treat peak wrist height as confirmed contact or ankle movement alone as proof of ground contact.

Use the existing outputs to debug the pipeline; rerun pose at original sample frame rate for finer event comparisons where needed. Retain actual video presentation timestamps rather than assuming every upload is constant-frame-rate. Report time error against the manual uncertainty intervals, detected/missed/unavailable events and results per clip. The 15-fps smoke run cannot substantiate a ±3-frame claim at 60 fps.

Completion check: automatic markers appear in the interface, match the intended visible phases on all three development clips within their reviewed tolerance intervals, and do not fill in unobservable events. If a detector fails, keep that failure visible and investigate before adding more event types. This is development performance, not held-out accuracy.

### 4. Add a narrow, evidence-linked feedback rule

Implement `analysis/feedback.py`. First support a positive loading-to-extension observation when the sequence is clear. Add one corrective review candidate only after reviewing a measurable condition and its failure cases; foot movement during the toss is a candidate, with toss timing independently established. Do not promise a foot-fault detector or infer ball-toss depth from body joints.

Each rule declares required view, required events/joints, evidence interval, unavailable conditions and its cue/drill template. Uncertain evidence yields a descriptive observation or request for another angle. The rule engine selects at most one supported item; it must not force a fault onto Federer or copy a sample's coach label into an automatic diagnosis.

Use deterministic wording first. No new model training is required. Optional language-model phrasing and speech come later, after the underlying observation is reliable. Avoid causal claims such as 'this made the ball go into the net' without outcome evidence. Do not compare phone 2D joint angles directly with the existing lifted 3D Djokovic distribution.

Completion check: feedback links to the actual frames and evidence used; missing evidence causes abstention; manual coach comments remain clearly attributed. Test incomplete clips, uncertain joints and inappropriate views as well as valid evidence.

### 5. Connect upload, person selection and processing

Build a bounded upload endpoint and a single-worker job queue around the shared result format. Use generated job ids and isolated directories, validate size/decodability/duration, preserve source audio when available, normalize display rotation, and show stage/error status in the page. Support seeking uploaded media through HTTP byte-range responses.

Start with one manually selected player crop per clip if automatic selection is ambiguous. The user can select the server once; do not silently choose the opponent. Then integrate the existing person detector and verify subject selection on the multi-person Federer/Sara clips. Surface tracking loss and ask for reselection when needed.

Use the phone's video-file/camera picker for initial capture. In-browser webcam recording is a follow-on because it requires a secure browser origin and additional permission handling; ordinary file upload avoids that dependency.

Completion check: upload a previously unprocessed clip and obtain a real result or a useful failure. Repeated submissions have separate ids; pending work does not overwrite another result; oversized, corrupt and interrupted uploads fail cleanly.

### 6. Move the processing stages onto the Ventuno and validate

Verify live board dependencies and services before changing deployment. Run decoding, cropping, ExecuTorch pose, event detection and feedback generation on the board using the existing tested model. The phone/browser renders the supplied video and keypoints. Reuse the current private connection; do not introduce public hosting.

Measure upload time, complete processing time, model time and memory separately. Save the original video, result JSON and execution log per test clip. Rehearse with a fresh phone recording; add manual reference marks afterward and record disagreements without retuning on it before reporting that first result.

Completion check: a phone upload yields playable, timestamped results while the Mac performs no analysis. Report the actual observed latency and remaining manual steps. If direct phone access is unavailable, test through the existing cable path and label phone delivery as still unverified.

## Verification and scope

Write focused tests before implementing event/rule behavior: timestamp mapping, missing events, confidence gating, wrong-person/occlusion handling, and rule abstention. Test API validation/job isolation and playback synchronization at their boundaries. Run existing repository tests when shared code changes, rather than repeatedly testing unrelated reference analysis.

Deliverables are the labelled development set, local review page, event/rule modules, repeatable processing command, and a per-clip inspection report. A separate held-out coaching benchmark is still needed before claiming accuracy. Training a phase model, ball/racket detection, live webcam streaming, speech, practice-set progress and MCU lights follow the first end-to-end flow.

Implementation starts with steps 1–2 so the next visible result is the approved wireframe populated with real videos, reviewed markers and honest evidence states. Steps 3–4 replace fixtures with computed results; steps 5–6 complete the capture-to-board flow.
