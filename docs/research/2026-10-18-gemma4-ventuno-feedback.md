# Gemma 4 feedback iteration on Ventuno

This implementation follows the manual clip review in [the exploration](2026-10-18-gemma4-coaching-exploration.md). These are development observations by the coding assistant, not an independent certified tennis-coach assessment or held-out accuracy benchmark.

## Product contract

A player should leave with **one thing to do next**, not a joint-angle reading. Feedback contains a visible observation, one short cue, a small drill, an observable check, replay timestamps and the relevant limitation. Raw measurements remain available in collapsed diagnostics. A professional's knee angle is not an ideal target.

The system prompt treats Gemma as a practical coach working from supplied evidence. It may choose a supported practice focus and explain what the task lets the player compare. Reviewed content supplies the cue, drill, success check and factual observation. The model cannot turn missing evidence into a fault, prescribe a different bend direction, or claim an unseen ball event. This is deliberately a limited coaching role; the model does not independently watch the video in the deployed path.

## Manual video review before model changes

| Clip | What is visible | Useful coaching direction | Automatic evidence limit |
|---|---|---|---|
| Bremen | Backward trunk lean during the upward swing, then arm recovery | Investigate toss placement with a side view before changing technique | Current tracking supports recovery; it cannot establish toss depth or reproduce this investigation |
| Sara | Late foot reposition close to the baseline around 1.50–1.80 s, followed by recovery | Check shoe clearance before takeoff with a low camera | Current tracker does not detect the baseline; no foot-fault or clearance diagnosis |
| Federer | Loading then extension in slow motion around 5.4–9.91 s; landing absent | Reinforce the bend-and-rise sequence | Current pose processing supplies no supported stages; the app abstains despite manually visible movement |
| Indoor racket clip | Bend then rise; overhead action is cropped; arm descent visible | Rehearse a repeatable finish and improve overhead framing | Intervening leg tracking is incomplete; only supported arm recovery is used |
| White-shirt shadow | Racket-free rehearsal, bend/rise and arm recovery | Finish before resetting; compare repeated relaxed motions | Missing leg tracking does not imply an incorrect bend |
| Black-shirt shadow | Racket-free rehearsal with visible bend/rise around 2.8–3.55 s | Keep one smooth bend-and-rise rhythm | Contact and ball outcome cannot be assessed |
| Stephen | Mostly repeated frames in a paused/scrubbed screen recording | Request the original uninterrupted recording | No reliable motion timing |
| Vishal | Small split screen with mostly repeated frames | Request original single-player footage | No reliable complete sequence or matched-angle comparison |

Manual review used full-frame contact sheets and denser event frames. No private video was uploaded to a hosted model. Local source sheets/raw experiment outputs are under `local/gemma4-exploration/` and `local/gemma4-iteration/`.

## Evaluation criteria

A response passes only if:

1. **Grounded:** its observation and timestamps agree with supported movement; missing tracking is not a fault.
2. **Actionable:** it gives a cue a player can follow, a short drill, and a specific thing to compare in the next recording. An angle or "improve technique" alone fails.
3. **Focused:** one appropriate supported task; no unrelated body instructions or list of corrections.
4. **Calibrated:** no inferred power, speed, spin, ball contact, toss-depth diagnosis, foot-fault call, guaranteed improvement, or ideal professional joint angle.
5. **Honest provenance:** an actual Gemma 4 response from Ventuno, with fallback visibly distinguished. Mac results do not count as board verification.

For repeated-frame clips, the explanation must discuss obtaining usable footage, not making the player's movement smoother. For shadow motions, feedback must remain about body practice without claiming a ball event. Stored body tracking does not classify whether a racket or ball is present, so deployed prompts cannot infer either.

The final implementation handles unsupported/repeated-frame recordings before inference. These are explicit recording-quality responses, not generated Gemma successes. The fixture also includes a counterfactual arm-only evidence mask, which must choose preparation and never invent leg advice.

The fixture keeps manual notes and expected labels separate from model input. It tests the best **supported** focus, not whether the tracker matches every preferred manual coaching observation. Coverage gaps above remain failures of the broader vision-to-coaching objective even when response validation passes.

## Experiments and implementation

- Mac E2B/E4B direct-frame probes produced generic praise, wrong early-frame citations and missed paused/split-screen clips. A contact-sheet E4B probe also invented a second stroke. This path was rejected; no Mac vision result is presented as Ventuno coaching.
- Replaced Gemma 3 integration with Gemma 4 E2B on Ventuno. Inference uses the ARM64 Ollama runtime, loopback HTTP executed over ADB, CPU-only generation, four threads and a 4096-token context. There is no Mac/cloud fallback and no NPU-performance claim.
- Runtime: Ollama **0.40.6** on `QCVENTUNO015` / AArch64. Model: `gemma4:e2b`, Q4_K_M, digest `b37049369adfe3d2b653af0ab301a062ca5cbe96ace6aa0d3f2559ee9b563fc2`. Installed bundle is about 4.6 GB. Board logs and `/api/ps` confirmed CPU inference and zero VRAM.
- First board pass produced supported focus IDs, but manual inspection caught misleading purpose statements: a paused recording received "Practice making one complete, smooth movement…", and other replies used "ensure" language. These became failing regression tests; prompt and validator were tightened before the next pass.
- A second board pass showed that an example explanation could be copied into the wrong task. The final prompt supplies a purpose for each candidate, removes the generic example, and validates focus-specific wording. Missing-evidence cases now bypass the language model entirely.
- The repeated-frame gate rejected Stephen/Vishal while retaining the other six source clips in the initial pixel probe. It is a narrow heuristic, not a general edited-video detector. Extreme slow-motion footage with duplicated frames can also be rejected.
- Model/card/prompt/evidence/video changes invalidate cache. Invalid, unavailable and busy responses are not cached. Evidence timestamps come from stored stages, never model-generated numbers.

## Reproduce

From the repository root, with the local recordings/results referenced by `web/processor/fixtures/coaching_eval.json` available:

```sh
web/processor/start_gemma4_ventuno.sh
.venv/bin/python web/processor/eval_coach.py --out local/gemma4-eval
.venv/bin/python -m unittest discover -s web/processor -p 'test_*.py'
```

The eval executes fresh generations on the board, writes the exact request/model digest/raw response/parsed feedback/timing, and exits unsuccessfully on a contract failure. It does not reuse the application cache. Read the outputs against the videos as well as the machine checks: lexical validation is not complete semantic verification.

See [Ollama's ARM64 runtime instructions](https://docs.ollama.com/linux#arm64-install) and [Gemma 4 model information](https://ollama.com/library/gemma4:e2b). Model weights and runtime artifacts stay outside Git.

## Final measured results

Final version: `gemma4-ventuno-coach-v5`. Eight real development clips plus one synthetic arm-only evidence mask were each checked twice. **Twelve fresh board generations passed the supported-focus, cue, explanation and content checks; six recording-quality responses bypassed Gemma.** These are eighteen functional/content checks, not eighteen model successes. The final explanations were manually read against their task purposes and reviewed footage.

Model response time in the final passes was 2.57–20.78 seconds (median 8.82 seconds), with repeated prompt context substantially faster. The first cold board request in the initial pass took 30.10 seconds. No inference timings from the Mac are included. Five of six motion clips received a supported practice plan; the Federer tracking gap withheld coaching. Both paused/split-screen clips requested usable footage. The synthetic arm-only mask received preparation feedback without knee advice.

Validation: 89 processor Python tests, 54 TypeScript tests, TypeScript checking and the Next production build passed. Final local requests, raw outputs, model digest, timings and manual notes are in `local/gemma4-iteration/final-evaluation.json`, `ventuno-final/`, and `ventuno-arm-only/`.

This is a usable bounded practice-feedback feature, not parity with an expert tennis coach. In particular, the richer Sara/Bremen investigations in the manual review remain outside automatic tracking capability. Translation and direct visual fault diagnosis remain unvalidated.

## Resume verification and runtime persistence

Fixed an evidence-link regression: seeking to 3.55 seconds now preserves the upward-swing stage instead of resetting to loading. The regression failed before the fix and passed afterward. Browser verification confirmed both the video time and selected stage, with Gemma provenance visible; screenshot: `local/gemma4-iteration/feedback-ui.png`. All 89 Python tests and 54 TypeScript tests pass; the production build including TypeScript checking also passes.

The resumed live check found the earlier detached server had stopped. Installed and enabled `djoker-gemma4.service` under the board user manager, with restart on failure and the same loopback-only, cloud-disabled settings. Updated the startup script to install this service and verify readiness. The board already has user lingering enabled. Service activation and enablement were verified; a physical reboot was not performed.

A fresh uncached generation after service installation passed the same rhythm/content checks in 44.65 seconds, including cold model loading. This is an additional successful generation beyond the twelve earlier final-eval generations; it also shows cold-start latency can exceed the earlier 30.10-second observation. Raw evidence is in `local/gemma4-iteration/service-smoke/`.
