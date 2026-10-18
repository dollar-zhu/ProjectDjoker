# Gemma 4 coaching exploration

Date: 18 October 2026. Scope: investigate useful feedback, draft reference responses and evaluate a local Gemma 4 experiment. Application and board model configuration are unchanged.

## Intended product

After a serve, answer: **What should I keep or change? What in this clip supports that? What should I try next, and how will I know whether it helped?**

Gemma 4 should select and explain one appropriate practice focus from reviewed movement evidence and a small coaching-content library. It should personalize the explanation to the player's experience and translate it without changing the underlying coaching decision. Translation alone would preserve the current lack of useful content.

The first experiment supplies reviewed text evidence. It does not claim automated visual coaching: observations made here by the reviewing assistant are richer than the app's current body-only tracking. Gemma 4's vision capability merits a separate experiment with frame sequences, independent labels and temporal tests.

## Why today's output is weak

- `web/processor/commentary.py:analyse_stages` only asks for a `focus_id`; rendering returns an existing observation and replay instruction verbatim.
- `web/processor/stages.py` provides descriptions such as knee angles and arm descent, not an actionable coaching curriculum.
- `commentary.py:prepare_evidence` has an older, exploratory ±15-degree pro-relative knee rule. Difference from a professional is not evidence that more or less bend will help this player.
- The Gemma 3 paths, tokenizer, `--decoder_model_version gemma3`, response delimiters, source labels and cache version are embedded in the current implementation. Changing the label would not upgrade the model.
- The existing research notes contain proposed thresholds and causal claims, explicitly marked provisional in places. They need review before becoming model instructions. A wrist landmark is not racket-ball contact; a slow-motion playback interval is not physical serve timing.

## Visual review and draft reference feedback

Method: sampled full-frame sequences from five existing development excerpts plus the most recent saved indoor clip; inspected denser crops around Sara's foot movement and Bremen's upward swing. Existing case notes were read before review: this is **not blinded**, independent expert validation, or a held-out test. Single serves do not establish recurring inconsistency. Times below are relative to each excerpt, and source slow motion is preserved.

### Bremen: investigate toss placement before prescribing a change

Clip: `benchmark/manual/samples/a001_bremen.mp4`, especially 0.65–1.20s (original source 14.45–15.00s). The torso leans back through the upward action. The rear-oblique camera and sparse ball samples do not resolve the depth of the toss reliably.

Reference response:

> Your backward lean makes toss placement worth checking before changing your knee bend. Film five comfortable serves to the same target from the side, with the ball and feet in frame. Look for a repeated backward reach. This angle does not establish that your toss is too far behind you.

The priority is a plausible question, not a confirmed root cause. A normal serve also includes trunk tilt. Do not diagnose an incorrect grip, injury risk, low power, or a toss distance from this evidence.

### Sara: a concrete foot-position experiment

Clip: `benchmark/manual/samples/a004_sara.mp4`, especially 1.50–1.80s (original source 142.00–142.30s). A late foot repositioning brings a shoe close to the baseline before takeoff. Shoe-line contact is not reliably resolved.

Reference response:

> Your foot moves close to the baseline just before takeoff. Try starting a little farther back and film five easy serves from court level, keeping your natural step. Check that your shoes stay visibly behind the line before takeoff. This clip does not settle whether you touched it.

This is a proposed practice experiment. A natural step or pinpoint stance is not itself a fault. Do not issue an officiating decision or tell all players to freeze their feet.

### Recent indoor recording: reinforce a visible sequence

Clip: `local/web-jobs/b4268da1-578a-43bb-8d52-00df33a75ac5/video.mp4`, especially 2.10–2.70s. Knee loading is followed by upward extension. The overhead racket/ball region leaves the frame. Saved pose evidence also reports loading at 2.35s and highest tracked wrist at 2.75s, but marks the intervening acceleration stage unavailable.

Reference response:

> You already have a visible bend-and-rise sequence. Keep it smooth for five relaxed shadow serves and compare whether the rise stays continuous. For the next recording, include space above the racket so we can review the overhead action; contact is missing here.

Do not call an unavailable pose stage a faulty swing. The five-repeat task checks repeatability; no improvement, shot result or power has yet been measured.

### Additional controls

- **Federer, 5.40–9.91s:** visible bend followed by extension. Reinforce the movement sequence. Do not invent a correction, report real-time speed from the slowed footage, or evaluate the absent landing.
- **Stephen, full 2.97s excerpt:** a front-oblique screen recording pauses/scrubs around preparation. Ask for an uninterrupted rear recording for the app's rear-view comparison. Do not diagnose poor rhythm from edited timing.
- **Vishal, full 4.00s excerpt:** two differently framed players in a small, mostly paused split screen. Ask for the original uninterrupted single-player clip. Do not infer hip over-rotation from mismatched views.
- **Synthetic missing-legs counterfactual:** remove all knee/ankle evidence. A valid answer must stop giving knee-bend advice and request framing that includes the legs.

## Content library needed

Start with reviewed cards for toss placement/consistency, loading-to-extension rhythm, foot organization, recovery balance, and capture quality. Each card needs:

1. Observable evidence required, supported camera views and contraindicating/missing evidence.
2. What the observation does and does not imply; whether a recurring pattern is needed.
3. One plain cue, a beginner task, progression and observable success check.
4. A source or explicit proposed-practice status, plus reviewer and revision.

Suggested output contract: evidence IDs + selected card + response type (`check`, `reinforce`, `recapture`) + observation + why + cue + practice + success check + limitation. Translate a checked answer as a separate step. Persist model/version, prompt/content revision and original language. A lightweight validator should reject unknown evidence IDs and unsupported numeric facts, but semantic coaching review is still required.

An appropriate cue can be an experiment: the model must not quietly turn “worth checking” into “your toss is definitely behind you.” A measurement difference is not automatically a defect, and “nothing needs changing from this evidence” must be a valid outcome.

## Predefined feedback evaluation rubric

Each dimension scores 0 (absent/wrong), 1 (partly useful), or 2 (clear and correct):

| Dimension | Full-credit requirement |
|---|---|
| Evidence grounding | Every observation is supported by a cited supplied evidence ID; proposed actions are not reported as observations. |
| Priority | One justified focus, reinforcement or filming task; no list of speculative defects. |
| Explanation | Explains why this focus is useful without asserting an unsupported cause or performance effect. |
| Actionability | An ordinary player can execute the cue and task immediately. |
| Success check | Concrete next-repetition or new-recording check, appropriate to available evidence. |
| Calibration | Retains material uncertainty; does not hide a guess behind confident wording. |
| Communication | Brief, natural, internally consistent, understandable without biomechanics jargon. |

Proposed development gate: at least **12/14**, no dimension at zero, and no critical failure. Critical failures override totals: invented measurement/contact/outcome, unsupported defect or causal diagnosis, treating unavailable tracking as bad technique, opposite correction direction, or fabricated source. This is our product threshold, not a published tennis standard.

Translation is a separate gate: preserve body part, direction, counts, timing, negation and uncertainty; use idiomatic tennis terminology; add no advice. Back-translation is only a diagnostic, not a substitute for review by a competent speaker.

Assess meaning rather than exact wording. The same assistant authors and grades these provisional references; a qualified tennis coach should review the content and a separate rater should assess a new held-out set before claiming coaching quality. Split by player/source, not adjacent clips from the same recording. Include varied skill, serve type, target, handedness, camera view, good serves and tracking failures. Test multiple runs; report critical failures separately from average scores. Track whether people understand and can perform the cue, and later whether their chosen outcome improves.

## Model experiment and deployment

Use **Gemma 4 E2B** for the initial local experiment, with E4B as a quality comparison if necessary. Google's model card describes E2B/E4B as edge-oriented multimodal models with multilingual support; that is capability documentation, not evidence of tennis accuracy or Ventuno compatibility.

Live board inspection on 18 October found the current Gemma 3 model folder and no Gemma 4 model under `/home/arduino/models`. The board's checked-out Qualcomm source explicitly lists `gemma4-e2b`, and `runner.cpp` handles `gemma4`; the installed local ExecuTorch package also contains Gemma 4 implementation files. This is a concrete migration path, but source support does not prove the currently built binary or a QCS8275-exported artifact works. Migration needs matching weights, tokenizer/chat template, export/backend, runner support, measured memory/latency and output validation on QCS8275. Keep Mac experimental results explicitly separate from board performance.

Experiment assets are in `local/gemma4-exploration/`: source-derived frame sheets, `cases.json` (reference answers), `cards.json`, requests, raw responses and evaluation notes. Reference answers and expected labels are withheld from model requests. The model receives reviewed facts and content cards, so successful results test synthesis/content selection, not independent video diagnosis. No private footage is uploaded; Ollama inference is local.

## Sources

- [Google Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Ollama Gemma 4](https://ollama.com/library/gemma4:e2b)
- [ExecuTorch source](https://github.com/pytorch/executorch)
- [USTA: Harness Your Serve](https://www.usta.com/en/home/improve/tips-and-instruction/national/tennis-troubleshooting--serve.html): toss release and placement principle; it does not label any of our clips.
- [USTA: Tips for a Consistent Ball Toss](https://www.usta.com/en/home/improve/tips-and-instruction/national/improve-your-tennis-game--.html): background for future toss-content cards, not evidence that this player's release is wrong.
- Existing video provenance: `benchmark/manual/samples/manifest.json`. These excerpts are development references, not licensed fine-tuning data.

## Observed experiment results

Actual local model: Ollama `gemma4:e2b`, model ID `b37049369adf`, Q4_K_M, 4.6 GB installed bundle, Ollama 0.35.1. Runs used temperature 0, seed 42, thinking disabled, context 8192, maximum 650 output tokens for a controlled development probe. This differs from Google's general sampling recommendation; it is not an optimized model benchmark.

| Experiment | Observed result | Interpretation |
|---|---|---|
| v1: reviewed facts + four available cards | All 7 outputs parse, use allowed evidence IDs and fit 110 words; only 4/7 select expected card and 5/7 select expected mode. | Valid JSON and valid IDs are insufficient: a model can cite real evidence and still give unrelated advice. |
| v2: reviewed fixed plan, free short cue | Bremen acquires **“Keep your torso upright.”** | Reject: the evidence supports checking toss depth, not correcting trunk tilt. |
| v3: reviewed fixed plan + exact approved cue | All 7 preserve the supplied cue, IDs, mode and card, and fit 110 words. Provisional manual scores 12–13/14 with no critical failure identified. | Promising as a language layer. Card/mode selection is supplied here, so 7/7 is **not** independent diagnostic accuracy. |
| Direct visual probe: indoor frame sheet | Generic “consistent kinetic chain” advice, no useful specific video-grounded priority. | This single probe does not justify direct visual fault selection; it is not an evaluation of all Gemma 4 vision configurations. |
| Mandarin translation, 3 iterations | First two need clearer direction/filming wording; clearer English source in v3 improves camera wording but changes “before takeoff” to “before serving.” | None accepted unchanged. Timing and direction need semantic checks, even when the translation sounds plausible. |

v3 measured wall time was 1.85–2.33 seconds per English response (median 2.04 seconds) on this Mac, with the model already loaded. These seven timings are a local smoke sample, not Ventuno/NPU or end-to-end app latency. Model execution, raw requests and responses are saved locally. No Gemma 3 call was used in these experiments.

Provisional rubric scores (same assistant that wrote the references; tune-set results):

| Case | v1 score / 14 | Critical v1 issue | v3 score / 14 |
|---|---:|---|---:|
| Bremen | 5 | Unsupported focus and power speculation | 13 |
| Sara | 11 | None; wrong response type and missing specific uncertainty | 12 |
| Federer | 12 | None | 12 |
| Indoor | 11 | None; overhead limitation omitted | 12 |
| Stephen | 6 | Unsupported toss focus | 13 |
| Vishal | 4 | Unsupported and conflicting practice tasks | 13 |
| Missing legs (synthetic) | 12 | None | 13 |

The final English answers are similar in meaning to the reference examples, but still repetitive and sometimes awkward. For Sara, “checks if you clear the baseline” is ambiguous next to an otherwise correct instruction to remain behind it; use reviewed wording in the visible explanation. For the indoor case, the explanation should say what rhythm practice achieves, rather than sounding as though cropped footage caused the choice of exercise. These are refinement targets, not hidden failures.

### Actual Gemma 4 output, v3, Sara (selected fields verbatim)

> A late foot repositioning moves a shoe close to the baseline before takeoff.
>
> Leave a little more room behind the baseline while keeping your natural step.
>
> Start a little farther behind the baseline; rehearse five easy serves and film the feet from court level.
>
> This clip does not reliably show whether the shoe touched the baseline.

### Actual Gemma 4 output, v3, indoor (selected fields verbatim)

> Your knee loading is followed by an upward extension during the indoor serve rehearsal.
>
> Keep one smooth bend-and-rise rhythm.
>
> Repeat five relaxed shadow serves with one smooth bend-and-rise rhythm.
>
> Compare the five clips for a continuous rise without an added pause.
>
> The overhead action leaves the frame, so contact and shot outcome cannot be judged.

### Recommendation after testing

Build the coaching-content layer first, with a reviewed decision and short approved cue. Use Gemma 4 E2B for explanation/adaptation, and assess E4B if we need more freedom in content selection or translation. Gate every response against its plan and show the reviewed fallback if it deviates. Treat translation as a separate evaluated feature; do not yet promise it preserves coaching meaning. The latest app remains on Gemma 3 until a separately verified Gemma 4 integration replaces the real runtime, not just the label.

Next evaluation should use fresh players/clips and a separate tennis coach, repeat generation, cover language invariants and compare against a plain content-card template. If Gemma does not improve usefulness over that template, do not add it to that part of the loop merely for model usage.
