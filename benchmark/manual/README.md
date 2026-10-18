# Manual serve benchmark — first review

Reviewed 17 October 2026. This is a development/reference set, not a validated test set or a source of numerical pro thresholds.

## What was actually inspected

Selected, timestamped frame sequences were visually inspected from downloaded public videos, including closely spaced frames around the chosen actions. Coaching captions/descriptions were read separately to attribute the coach's stated diagnosis. Entire lessons were not watched continuously or listened to. The coach labels were known during review, so this is not an independent blinded assessment. No pose model was used to generate these observations.

Times below refer to the original YouTube video's playback clock, not biomechanical time. Edited slow motion, replays, pauses, and analysis screens make these videos unsuitable for measuring real movement speed. One serve replayed many times is still one example. The source videos remain copyrighted by their owners; cache files are local analysis inputs, excluded from Git. Local review excerpts are omitted from Git; source links and timestamps below identify the evidence.

## 1. Federer — positive movement reference

Source: [Topspin Tennis, Federer 1st Serve (Rear View) | Master Class, 00:10–00:20](https://www.youtube.com/watch?v=f0gnXSwrK00&t=10s).

**Camera:** rear-oblique; full body visible in the selected sequence, although feet approach the lower frame edge. The clip cuts away just after the upward swing. A second player is visible on the left, making correct-person tracking a useful test.

**Visible evidence:**

- 00:10–00:12: setup and toss; feet remain separated in a platform stance.
- 00:14–00:16: knees are flexed and the tossing arm is raised; the shoulder line is visibly tilted.
- 00:18–00:20: knees extend, the body rises, and the hitting arm reaches overhead. Both feet become airborne.
- Landing is not shown in this selected excerpt. Ball/racket contact has not been labelled to an exact frame.

**Manual feedback:** “Your loading position leads into a clear upward extension. Keep that sequence. This excerpt ends before landing, so I can't assess the recovery.”

**Expected app behaviour:** show the loading-to-extension sequence; track Federer rather than the player at the left; do not invent a fault just to fill the feedback panel. Do not score landing or prescribe Federer's exact stance, shoulder angle, or jump height as a universal target. This is a positive reference for these particular observations, not a declaration that every aspect of the serve is perfect.


## 2. Bremen — toss review, with a view limitation

Source: [Intuitive Tennis, Tennis Serve Masterclass | 3.5 NTRP Lesson, 00:14–00:16](https://www.youtube.com/watch?v=-zEmDTe_KT4&t=14s). Coach's diagnosis: [01:04–01:21](https://www.youtube.com/watch?v=-zEmDTe_KT4&t=64s).

**Camera:** rear-oblique in the serve excerpt, with body, ball and baseline visible. The lesson also cuts to side/front views. The original CSV's 00:58–01:18 interval mainly contains discussion, not the serve we need to analyse.

**Visible evidence:**

- 00:14.3–00:14.7: the ball rises from the tossing hand while the body prepares.
- 00:14.9: the head and upper trunk are tilted back while the racket is behind the head.
- Around 00:15.0: the ball is close to the overhead racket; do not treat this sampled frame as verified contact.
- 00:15.1–00:15.7: follow-through and small recovery steps near the baseline.

**Coach label:** the toss goes too far behind the head/body; Nikola Aracic asks Bremen to place it farther into the court and allow a forward lean. This is a coach-attributed diagnosis. The rear-oblique pictures alone do not establish exact front/back toss depth or prove that the toss caused a particular miss.

**Manual feedback:** “Your head and upper body tip back as you reach for this toss. Check the toss from the side before changing the rest of the motion. Your coach's correction here is to place it a little farther into the court.”

**Expected app behaviour:** identify this as a toss-placement review candidate, not a confident left/right toss fault. Request a side view before making a depth diagnosis. A body skeleton alone cannot measure ball toss placement. Do not convert 'behind the head' into 'left drift'; do not claim a net error, serve speed, centimetres of depth, or spin from these frames.


## 3. Sara — foot-placement review on a rear view

Source: [Intuitive Tennis, Tennis Serve Masterclass with D1 Player Sara, 02:21–02:23.2](https://www.youtube.com/watch?v=Om84TmRk2i0&t=141s). Coach's diagnosis: [02:23–02:50](https://www.youtube.com/watch?v=Om84TmRk2i0&t=143s); timing explanation around [03:36–03:58](https://www.youtube.com/watch?v=Om84TmRk2i0&t=216s).

**Camera:** rear-oblique, with both feet, baseline, and upper body visible. A coach on the right is another distractor for person tracking. Sara is described as a D1 player by the source; she is an advanced non-tour example, not a beginner.

**Visible evidence:**

- 02:21.0: setup close to the baseline.
- 02:21.4–02:22.2: toss and foot movement before takeoff. At approximately 02:22.2 the shoes are very close to/overlapping the baseline in the image.
- 02:22.4–02:22.6: upward swing and airborne body.
- 02:22.8–02:23.2: landing and recovery inside the court.

**Coach label:** foot fault, associated with a late step after the toss begins. Auto-captions mistranscribe some occurrences as 'footballs'; surrounding explicit mentions of 'foot fault' make the intended coaching topic clear.

**Manual feedback:** “Check your late step during the toss: your shoe reaches the baseline before the upward swing. Rehearse the foot placement with visible clearance behind the line, then check another serve.”

**Confidence:** medium for the visual foot-placement concern. The coach's diagnosis is explicit, but the compressed frame does not support a definitive officiating call about exact shoe-ground contact. Landing inside the court after the strike is not the event being flagged.

**Expected app behaviour:** show the pre-takeoff shoe/line evidence; offer a foot-placement review with uncertainty. Do not infer foot fault merely from an ankle coordinate crossing a line or from the post-strike landing. Reliable automatic confirmation needs court-line and shoe-ground-contact evidence in addition to body joints.


## 4. Stephen — useful coaching example; exclude from rear-view evaluation

Source: [Meike Babel, Tennis Serve Analysis 3.5 USTA player, 04:40–05:00](https://www.youtube.com/watch?v=VfuC22ejLUE&t=280s); foot discussion around [05:29–06:30](https://www.youtube.com/watch?v=VfuC22ejLUE&t=329s).

**Camera:** front/oblique, not rear. The player is small within a portrait recording embedded inside an analysis screen.

**Visible evidence:** at 04:55 the loaded pose has a relatively modest visible shoulder tilt despite a high tossing arm. The analysis alternates setup/loading frames while discussing foot movement. The published comparison later introduces Andy Murray from a different view; raw angles across these views are not comparable.

**Coach label:** increase shoulder-over-shoulder organisation in the loading position and keep the feet better organised. The prior CSV incorrectly credited 'Micah' in its notes; the source is Meike Babel.

**Manual feedback:** “Review the loading position: raising the tossing arm is not the same as tilting the shoulder line. Rehearse the loaded position your coach demonstrates, and keep the foot placement repeatable.”

**Expected app behaviour in our rear-view workflow:** ask for a rear recording rather than run rear-view thresholds on this image. Keep this as a view-rejection test and a coaching-language example, not a scored rear-view fault case.


## 5. Vishal — exclude from the initial automatic benchmark

Source: [Meike Babel, Vishal serve analysis](https://www.youtube.com/watch?v=RRm7AQo4x4I&t=180s).

Overview frames at 01:20, 03:00, 04:00, 05:00 and later show an edited split-screen comparison. The amateur is small, filmed from a low oblique angle; the lower body reaches the bottom edge. The comparator is a much higher camera view. These are poor inputs for a clean rear-view full-body measurement benchmark.

The old CSV's hip-loading/over-rotation label remains coach-sourced. I have not independently validated that causal diagnosis from these overview frames. Expected behaviour: reject this screen recording for quantitative comparison and request the original full-body clip. Do not grade pronation or infer three-dimensional hip rotation from the overview.


## What this changes about the build

The first useful benchmark is a set of evidence-and-response cases, not a single ideal pro skeleton:

| Case | What should be tested | Expected result |
|---|---|---|
| Federer 00:10–00:20 | Correct person, load-to-extension sequence, missing landing | Describe the visible positive; abstain on landing |
| Bremen 00:14–00:16 | Toss/body relationship and depth ambiguity | Flag a review candidate; ask for side-view confirmation |
| Sara 02:21–02:23.2 | Feet relative to baseline before takeoff | Flag foot-placement concern; expose uncertainty |
| Stephen 04:55 | Wrong camera view | Reject rear-view scoring |
| Vishal comparison | Small/cropped player and mismatched views | Reject quantitative comparison |

The minimum report must link each observation to frames, separate visible evidence from coach interpretation, show when it cannot judge, and avoid confusing a later consequence with the claimed cause. RTMPose body joints alone do not supply a ball, racket, shoe outline, or court calibration.

### Acceptance rubric for the first implementation

1. Select the intended server and preserve the source time and camera view.
2. Display the supporting sequence, not just one flattering or misleading still.
3. Match the response category above: positive observation, review candidate, or abstention.
4. Never add unsupported outcomes, exact contact frames, centimetres, spin, or causal claims.
5. Keep coach-labelled diagnosis and model-visible evidence separate.

The labels are provisional. Before reporting accuracy, collect unseen eligible full serves, obtain an independent coach review, define acceptable alternate diagnoses, and keep held-out players/videos separate from these development examples. Multiple excerpts of one lesson must not be counted as independent validation. No pass percentage, angle band, or model coaching-accuracy claim follows from this review.
