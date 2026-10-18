# On-device Tennis Serve Coach — Checkpoint Research

Compiled for a 2-day hackathon build. System inputs are strictly: COCO-17 2D
keypoints (nose, L/R eye, L/R ear, L/R shoulder, L/R elbow, L/R wrist, L/R
hip, L/R knee, L/R ankle) from a phone-filmed slow-motion serve, SIDE-ON or
BEHIND the server, plus four derived events — **ball-contact frame** (audio
onset), **toss-apex frame** (yellow-ball colour filter), **deepest-knee-bend
frame**, and **landing frame**. No racket keypoints, no 3D, no grip/finger
detail.

**Sourcing method note (read before trusting numbers):** I could fetch and
read full text/abstracts for the peer-reviewed sources below directly
(PubMed/PMC APIs and one coaching-site page loaded live in this session).
General web search engines (Google, Bing, DuckDuckGo) returned blocked or
unrelated pages in this environment, and Brave Search rate-limited after a
handful of queries, so coverage of the specific named coaching channels
(Top Tennis Training, Intuitive Tennis, Tennis Evolution, 2MinuteTennis) is
**thinner and flagged as recalled-from-general-knowledge, not live-verified
this session**, wherever it appears below. Where I could not verify a
number from a fetched primary source, I say so explicitly and label it
"coach consensus / no peer-reviewed number found" per the task's
instruction, and propose a 2D proxy with a stated assumption.

---

## 0. Primary sources actually retrieved and read this session

| # | Citation | What I pulled from it |
|---|---|---|
| S1 | Kovacs M, Ellenbecker T. "An 8-Stage Model for Evaluating the Tennis Serve: Implications for Performance Enhancement and Injury Prevention." *Sports Health*. 2011;3(6):504-513. doi:10.1177/1941738111414175. PMID 23016050. Full text: https://pmc.ncbi.nlm.nih.gov/articles/PMC3445225/ | The 8-stage model (Start, Release, Loading, Cocking, Acceleration, Contact, Deceleration, Follow-through grouped into Preparation/Acceleration/Follow-through phases); toss-lateral-offset guidance; front-knee-flexion-in-loading threshold (>15°); foot-up vs foot-back knee kinematics; max-external-rotation (MER) joint angles. **Note:** the live fetch of this article only rendered the Preparation phase (stages 1-4) narrative text in full; stages 5-8 (acceleration/contact/deceleration/follow-through) were not retrievable as body text in this session (page kept returning the same truncated render), so direct quotes about stage 6 "Contact" and stage 8 "Landing" come from the *abstract/model description* and cross-source corroboration (S2, S3), not from reading that section's full paragraph. Flagged inline below. |
| S2 | Fleisig G, Nicholls R, Elliott B, Escamilla R. "Kinematics used by world class tennis players to produce high-velocity serves." *Sports Biomechanics*. 2003;2(1):51-64. doi:10.1080/14763140308522807. PMID 14658245. | 3D motion capture of 20 players at Sydney 2000 Olympics. MER joint angles, order/magnitude of peak angular velocities, impact-instant trunk tilt/arm abduction, ball speeds by sex. |
| S3 | Elliott B, Fleisig G, Nicholls R, Escamilla R. "Technique effects on upper limb loading in the tennis serve." *Journal of Science and Medicine in Sport*. 2003;6(1):76-87. doi:10.1016/s1440-2440(03)80011-7. PMID 12801213. | Same Sydney 2000 dataset: front-knee-flexion-in-backswing magnitude compared against shoulder/elbow joint torques; shows more knee flexion correlates with lower injury-risk torque at similar serve speed. |
| S4 | Reid M, Whiteside D, Elliott B. "Serving to different locations: set-up, toss, and racket kinematics of the professional tennis serve." *Sports Biomechanics*. 2011;10(4):407-414. doi:10.1080/14763141.2011.629206. PMID 22303790. | Front-foot position, toss-apex position, and ball-impact position change significantly with first-serve target location (T/body/wide) but are consistent across second serves. |
| S5 | Reid M, Whiteside D, Gilbin G, Elliott B. "Effect of a common task constraint on the body, racket, and ball kinematics of the elite junior tennis serve." *Sports Biomechanics*. 2013;12(1):15-22. doi:10.1080/14763141.2012.724702. PMID 23724604. | "Serve from the knees" drill kinematics — used below for the leg-drive drill entry. |
| S6 | Reid M, Whiteside D, Elliott B. "Effect of skill decomposition on racket and ball kinematics of the elite junior tennis serve." *Sports Biomechanics*. 2010;9(4):296-303. doi:10.1080/14763141.2010.535843. PMID 21309303. | Practising the toss in isolation significantly raises toss height vs full serve, and breaks the racket/ball temporal coupling (r=0.861 in full serve) — a caution about decomposed toss drills. |
| S7 | Whiteside D, Elliott B, Lay B, Reid M. "Coordination and variability in the elite female tennis serve." *Journal of Sports Science*. 2015;33(7):675-686. doi:10.1080/02640414.2014.962569. PMID 25358037. | Lower-limb/trunk coordination is most consistent at the instant players leave the ground; elbow-DOF variability rises near impact as a compensation mechanism; temporal structure of the serve is stable despite toss variability. |
| S8 | Feel Tennis Coaching (Tomaz Mencinger). "Tennis Serve Video Analysis And Drills For A Higher Toss." https://www.feeltennis.net/serve-higher-toss/ (fetched live, undated post, accessed 2026-10-17). | Coaching heuristic: toss apex "about 1 racket length above the contact point" as a practical target; low toss + collapsing tossing arm as a linked fault pair; named exceptions (Karlovic, Dolgopolov) who serve well off a low toss. |

Kovacs & Ellenbecker 2011 is the Sports Health paper the brief calls out by
name; Reid/Whiteside/Elliott/Fleisig/Escamilla papers (S2–S7) are the
"Elliott, Reid, Whiteside biomechanics papers" the brief asks for — these
are the real underlying Australian Institute of Sport / Tennis Australia /
UWA research group outputs, mostly using the Sydney 2000 Olympics motion
capture dataset or Tennis Australia's VICON lab. I did not find a
retrievable, distinctly-titled "ITF Coaching & Sport Science Review"
article with hard numbers in the time available (its site returned 403 to
automated fetches); where the brief's example numbers (contact height
≈1.5× standing height, front knee 100-120° at deepest bend) could not be
traced to one of S1–S8, I label them **"coach consensus, no primary
citation located this session"** below, consistent with the brief's own
fallback instruction.

---

## 1. Checkpoint table

Conventions used in the "Metric" column: all joint angles are the
**included angle** at the joint (angle between the two adjacent segments,
180° = straight), computed from 2D COCO-17 keypoint coordinates in the
image/pixel plane (no depth) unless stated otherwise. "Hip width" =
pixel distance between L-hip and R-hip keypoints in the relevant frame,
used as the in-frame scale reference since standing height is hard to
pin down once the player crouches; "shoulder width" is used as an
alternate scale reference at trophy/contact when hips are foreshortened
in the rear view.

| # | Stage | Metric (2D COCO-17 + events) | Pro range / amateur-fault threshold (source) | Side? | Rear? | Root-cause chain | External-focus cue | Camera-gradable drill (source) | Pass rule |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Setup | **Stance width at setup**: ankle-to-ankle horizontal pixel distance at the Start frame (S1 stage 1), normalised by hip width at the same frame. | No peer-reviewed 2D number found. Coach consensus (S1 describes "foot-up" vs "foot-back" as the two stance families but gives no width threshold): foot-up ≈ feet together before loading, foot-back ≈ a wider, more side-on base that "permits greater squat depth" (S1, Loading section, citing ref. 48 inside S1). **Proposed 2D proxy/assumption**: flag foot-back if stance width > 1.3× hip width at Start, since S1 attributes greater front-knee extensor range in foot-back stance to "a wider base of support" — assumption stated, not a literature threshold. | Yes, feet visible on ground plane | Partly — rear view foreshortens front-back foot separation; can still see left-right stance width | Over-narrow stance → less stable base → inconsistent toss placement → rushed cocking | "Step into a comfortable, balanced starting position, like you're about to throw a ball at a target." | Record 5 setups from fixed camera; measure ankle-to-ankle / hip-width ratio consistency across reps (no external source — proposed by me as the simplest camera-only gradable version of a stance check). | Ratio within ±15% of player's own median across last 5 serves (consistency, not an absolute pro band, since no literature band exists). |
| 2 | Toss (release) | **Toss-apex horizontal offset**: at the toss-apex frame (yellow-ball event), horizontal pixel offset of the ball from the front-toe keypoint (side view = depth into the court) or from the vertical line through the front-hip/shoulder midpoint (rear view = left/right drift), normalised by hip width. | S1 (Release, stage 2): toss should be released "slightly lateral to the overhead position of the server," targeting ball contact at **~100° of arm abduction** (S1, citing ref. 29 = Fleisig 2003/S2-adjacent source); toss too close to the head ("12 o'clock position") increases abduction and subacromial-impingement risk (S1). S4 (Reid/Whiteside/Elliott 2011): toss-apex (ball zenith) position shifts **significantly** with target location on first serves (T/body/wide) but is the one parameter players vary intentionally — so "toss drift" must be judged against the player's own repeated T-serve toss, not a single universal number. **No explicit degrees/cm threshold for "toss too far behind the head" found in the fetched sources — coach consensus fallback used**: flag if the toss apex sits behind (side view, toward the back fence from) the front-toe line by more than ~0.3-0.5× hip-width, an assumption I am stating explicitly, not sourced. | Yes — primary depth-offset view | Yes for L/R drift, no for depth-offset (camera axis aligned with the offset you most care about, side view) | Toss behind head/body → forces trunk to chase the ball → late, cramped contact → serve into net or short | "Place the toss right where you want to reach up and 'pick an apple' just in front of you." | Tennis Australia / S4-style repeated-target drill: serve 10 reproducible T-serves and check toss-apex pixel position is within band for ≥8/10 (S4 shows elite pros *do* hit a consistent toss position per target — gradable consistency check). | Toss-apex offset within player's own ±0.3 hip-widths band on 8 of 10 reps. |
| 3 | Toss (release) | **Toss height proxy**: vertical pixel distance from toss-release wrist keypoint to toss-apex ball position, normalised by the player's own standing-height pixel estimate (nose-to-ankle distance at Start frame). | S8 (Feel Tennis, live-fetched): practical coaching target is **toss apex ≈ 1 racket length above the contact point** (~0.686 m, standard racket length), described as "a good guideline," with named exceptions (Karlovic, Dolgopolov serve well off a *lower* toss with a faster rhythm) — S8 explicitly frames this as guideline, not hard law. S6 (Reid/Whiteside/Elliott 2010) found that practising the toss **in isolation** raises the ball's zenith significantly above where it lands during a *real* serve — meaning a toss-height checkpoint must be measured during full serves, not decomposed toss-only reps, or the system will mis-calibrate. | Yes | Partly — vertical toss height is visible from behind, but the racket is not tracked, so "1 racket length" cannot be computed without a size reference; propose converting to "≈0.4-0.5× standing height above contact" as 2D fallback (inference, stated). | Toss too low → rushed/tense loading and cocking (collapsing non-hitting arm per S8) → shallow racket drop (unobservable, no racket) → early/weak contact. Toss too high → ball drops before contact → timing drift, deceleration of racket before impact. | "Toss the ball to a spot in the air and let it hang there for a moment before you reach up." | Feel Tennis style side-by-side video comparison (S8): overlay toss trajectory across reps; flag the serve if toss apex is reached and ball is clearly descending for >X frames before contact (rushed-vs-hanging toss) — S8 demonstrates this exact side-by-side analysis method. | Apex height within player's own ±15% band on 4 of last 5 serves AND ball still within 2 frames of apex at contact. |
| 4 | Trophy | **Front-knee included angle at the trophy/cocking frame** — operationally the frame nearest the player's maximum-external-rotation cocked position, approximated on 2D pose as the frame where the hitting wrist is at its highest point *before* the forward swing begins (see Section 4 for the operational definition and its failure modes). | S1/S2/S3 (same Sydney 2000 dataset): at MER, elbow flexed **104°±12°**, shoulder abducted **101°±13°**, horizontally adducted 7°±13°, externally rotated 172°±12°, wrist extended 66°±19° (S1 citing S2's ref. 29; S2 reports the same 104°/172° figures independently — cross-validated). S3: front knee flexion **during the backswing** compared as 7.6° (low-flex group) vs **14.7°** (high-flex group) — both groups served at a similar ~162 km/h, but the 14.7° group had lower internal-rotation and varus elbow torque, i.e., **more front-knee flexion is protective, not just cosmetic** (S3). S1 independently states **front-knee flexion >15° in loading is recommended** for effective leg drive (S1, citing a different ref. 21) — consistent with S3's 14.7° "better" group. **Caveat**: these are knee-flexion-*amount* (change from standing) numbers, not an absolute included angle in degrees at the trophy frame — I could not find an absolute included-angle band (e.g., "120-140° included angle") for the front knee specifically at trophy in the sources I could read; the 100-120° *deepest-bend* figure in the brief's own example refers to a different, later frame (see row 6 and Section 6). | Yes — knee angle is a side-view-friendly 2D angle | Partly — rear view can see flexion but foreshortens true sagittal angle; usable as a coarse yes/no, not a precise degree readout | Insufficient knee flexion at trophy → no elastic loading → leg drive (row 6) is initiated from a "dead" position → shoulder/arm compensate with extra internal rotation torque (S3) → elevated elbow/shoulder injury load and lower reachable contact height | "Load into the court like you're about to jump and touch something above you." | Side-by-side comparison against the player's own best-rated serve (S8-style method): overlay trophy-frame pose, measure front-knee included angle delta. | Front-knee flexion-from-standing ≥15° (S1 threshold) on 4 of last 5 serves. |
| 5 | Trophy | **Shoulder-line tilt angle at trophy** (hitting shoulder below non-hitting shoulder): angle of the line between L-shoulder and R-shoulder keypoints relative to horizontal, at the trophy frame. | S1 (Loading, Figs. 8-9): "shoulder and pelvis lateral rear tilt before the cocking phase is a feature of powerful servers," creating a shoulder-over-shoulder rotation that "allows for greater racket height" (S1, citing ref. 48) — described qualitatively, **no degree value given** in the text I could retrieve. **Coach consensus / proposed 2D proxy (my inference, flagged)**: treat the hitting-side shoulder as "below" the non-hitting shoulder by at least a small positive tilt (e.g., >5-10° toward the hitting side) as a pass signal, since S1 only establishes the *direction* (tilted, hitting side low) and the *function* (bigger shoulder-over-shoulder rotation = more racket height), not a numeric band. | Yes, if the player isn't rotated too far away from camera | Yes — rear view actually isolates shoulder-line tilt cleanly since both shoulders are visible without foreshortening | No shoulder tilt → no shoulder-over-shoulder rotation available at acceleration → less racket-head height generated → serve into net or contact point too low/forward | "Reach the ball with your hitting shoulder, like you're climbing a ladder rung above you." | Compare shoulder-line tilt angle between player's trophy frame and a reference pro frame (qualitative overlay, since no numeric band exists — flagged). | Tilt angle present and consistent in direction (hitting shoulder lower) on 4 of last 5 serves; exact degree threshold left as a tunable, not literature-sourced. |
| 6 | Leg drive | **Front-knee included angle at the deepest-knee-bend event** (system-provided event). | Brief's own worked example (not independently found in S1-S8 during this session): "front knee flexion ~100-120°". I could **not** locate this exact band in the primary sources read this session; S1/S3's numbers (rows 4) are *amount of flexion from standing*, not an absolute included angle at deepest bend. **Labelled: coach consensus / commonly cited coaching heuristic, not confirmed against a specific peer-reviewed figure in the sources fetched this session.** It is, however, in the same ballpark as general lower-limb loading literature for jumping/throwing athletes (parallel domain, not tennis-specific, so treated as weak support only). | Yes — core side-view angle | Partly — same foreshortening caveat as row 4 | Too little bend (near-straight knee, included angle >150-160°, inferred cutoff) → leg drive is "arm-only," no vertical ground-reaction-force contribution (S1: "elite servers have greater vertical and horizontal force production... compared with beginner servers," citing ref. 32) → low contact height, power from arm/shoulder only → elevated shoulder/elbow load and lower ball speed for given effort | "Push the ground away and jump up to meet the ball at the top of your reach." | Compare deepest-bend frame knee angle across reps; use player's own best 20% of serves (by resulting ball speed/depth, if measurable) as the target band rather than an unverified universal number (explicit mitigation for the uncertain literature threshold). | Knee angle within player's own best-quintile band on 4 of last 5 serves. |
| 7 | Leg drive | **Hip-shoulder separation proxy (rear view)**: angle between the hip-line (L-hip–R-hip) and shoulder-line (L-shoulder–R-shoulder) at the end of the leg-drive event (frame just before forward swing/acceleration begins). | No 2D-pose-derivable peer-reviewed number found; true "X-factor" hip-shoulder separation in the literature is measured in 3D trunk axial rotation, not a 2D line-angle proxy. S1 does discuss trunk rotation and lateral flexion qualitatively (stage 3 Loading / stage 4 Cocking text) but gives EMG-timing findings, not a separation-angle band. **Coach consensus, no number — proposed 2D proxy with stated assumption**: use the 2D angle between the two shoulder-width lines as a rough stand-in for axial separation, acknowledging that foreshortening and out-of-plane rotation make this proxy noisy and directional-only (bigger = more separation), not quantitatively comparable to any published 3D X-factor value. | Partly — only usable if trunk hasn't rotated out of the hip-line's visibility; mostly a rear-view metric | Yes — primary intended view | Low separation → trunk/arm must generate speed without the stretch-shorten assist from the lower body → S1 notes efficient "kinetic chain" transfer depends on this sequencing (general statement, not this specific angle) → lower ball speed, more arm-dominant (and higher-injury-risk) swing | "Turn your back hip and chest away from the net, then unwind toward your target." | Track hip-line/shoulder-line angle time series across the serve; flag if the angle never exceeds the player's own 80th-percentile value from their best-rated reps. | Separation angle within top 20% of player's own historical distribution on 4 of last 5 serves (self-referential pass rule, since no universal band exists). |
| 8 | Contact | **Contact-point horizontal position relative to front toe (side view)**: horizontal pixel offset between the hitting-wrist keypoint at the ball-contact frame (audio-onset event) and the front-ankle/toe keypoint, normalised by hip width. | S4 (Reid/Whiteside/Elliott 2011): ball-impact position (and front-foot position) differ significantly by serve target — e.g., "players impacted the ball further left in the wide serve compared to the T serve" — meaning a single contact-x number is target-dependent and should be benchmarked per intended serve location, not universally. S2 (Fleisig 2003): "at impact, the trunk was tilted 48° above horizontal" and "the arm was abducted 101°," consistent with a contact point that is in front of and above the body, not directly overhead. No fetched source gives a precise "contact X cm in front of front toe" band. **Coach consensus fallback**: contact should be in front of the front foot/baseline, not behind it or directly overhead — directional check only, flagged as not independently numerically sourced. | Yes — primary intended view for this metric | No — depth-into-court offset is not resolvable from directly behind the player (front-to-back foreshortening) | Contact behind the front foot ("contact too far back/overhead") → arm must pull the racket through late → net-cord misses and reduced power, per the "toss behind the head/body" chain in row 2 | "Reach out and up, like you're picking an apple from a branch just in front of you." | Measure contact-x consistency across reps aimed at the same target (controls for S4's target-dependence). | Contact-x within player's own ±0.3 hip-width band for serves to the same target, on 4 of last 5. |
| 9 | Contact | **Contact-wrist height / standing height**: vertical pixel distance from ground (ankle keypoint, ground-contact frame nearest in time) to hitting-wrist keypoint at the ball-contact frame, divided by standing-height pixel estimate (nose-to-ankle at Start). | Brief's own example figure: "contact height ~1.5x standing height." **I could not confirm this exact multiplier in S1-S8 this session — labelled coach consensus / commonly cited heuristic, no primary citation located.** A consistency cross-check: S2 reports arm abduction 101° and trunk tilt 48° at impact, which is compatible with a contact point well above standing height but does not itself yield a multiplier without a racket-length/arm-length assumption I cannot verify against a fetched source. Treat 1.5× as an unverified but plausible planning number; do not present it to a user as peer-reviewed. | Yes | Partly — vertical height is visible from behind, but foot/ground occlusion by the body is more likely in rear view | Low contact height → associated with insufficient leg drive (row 6) and/or toss too low/behind (rows 2-3) → reduced racket-head speed at impact and flatter trajectory over the net → more net misses | "Reach as high as you can, like touching the ceiling with the racket." | Track contact-height ratio across reps; compare against the player's own best-outcome serves. | Within player's own top-quintile band on 4 of last 5 serves. |
| 10 | Landing | **Landing foot and side**: at the landing frame (system event — first frame the front-foot ankle's vertical pixel position stops decreasing after contact, see Section 4), identify which ankle keypoint is lower (closer to the ground-plane baseline y-coordinate) and whether it falls inside the baseline line if that line is visible/calibrated in frame. | S1's model names "landing" as stage 8 but the full paragraph on landing specifics was not retrievable in this session (see Section 0 caveat); S1's Loading-stage text does state that "large horizontal braking forces are developed with the front foot at landing," and separately that "the foot-up serving technique requires eccentric training of the lower body for landing" — i.e., S1 treats landing-foot loading as a trained quality, not a pass/fail position, and gives no degree/inch threshold. No source here gives a specific "front foot must land X cm inside the baseline" number. **Coach consensus fallback**: landing on/forward of the serve line with the front (lead) foot is typical for platform/pinpoint servers following through into the court; landing on the back foot is unusual and often linked to insufficient weight transfer — directional, not numerically sourced. | Yes, if the baseline is in frame and camera is stable/calibrated | Partly — left/right foot identity is easy from behind; "inside/outside the baseline" depth judgement is not, without a calibrated court line | Landing on the trail/back foot or stepping backward → indicates insufficient forward weight transfer during leg drive/acceleration → reduced power and a "blocked," arm-only swing (ties back to row 6) | "Chase the ball into the court after you hit it." | Track ankle y-position time series after contact; confirm monotonic decrease-then-plateau defines landing, and log which foot. | Front/lead-foot landing identified on 5 of 5 serves (simple binary check; foot-fault/baseline distance not gradable without a calibrated court line — flag as out of scope rather than guessing a threshold). |
| 11 | Leg drive / Trophy (stance type) | **Back-foot slide / platform vs pinpoint classification proxy**: track rear-ankle keypoint horizontal displacement, as a fraction of hip width, between the Start frame and the trophy frame — large convergence toward the front ankle suggests pinpoint stance, little movement suggests platform stance. | S1 names only "foot-up" and "foot-back" as its two technique families (quoted in row 1/4), which map loosely to the commonly used "pinpoint" (foot-up, back foot slides up to front foot before loading) and "platform" (foot-back, both feet stay apart through loading) terms used by coaches, but **S1 does not use the words "pinpoint" or "platform" in the text I could retrieve** — this mapping is my own inference from the described mechanics, flagged. S1 does give: foot-back → greater front-knee extension range (65.5°±12.6° vs 54.1°±11.7°) and greater squat depth; foot-up → greater rear-knee extension range (59.4°±6.6° vs 44.8±8.3°) and higher rear-knee peak angular velocity (9.3±1.2 vs 7.2±0.9 rad/s) and higher vertical ground reaction force / greater height reached; **ball velocity is not significantly different between the two techniques** (all S1, citing refs 27, 48). | Yes | Partly — foot convergence is visible but depth component (front-back) is foreshortened from behind | Neither stance is a "fault" per S1 (ball speed is unaffected) — this is a style classification, not a pass/fail checkpoint, so it should inform which other thresholds to apply (e.g., different expected front/rear knee ranges) rather than itself being flagged as an error. | "Pick the back-foot style that lets you load like you're about to jump the highest you can." | Classify stance type automatically from rear-ankle displacement, then apply the stance-appropriate knee-range expectations from S1 rather than a single universal band. | Not a pass/fail row — informational classification only, feeding rows 4/6/11's threshold selection. |

---

## 2. Fault priority tree

```
Setup → Toss → Trophy → Leg drive → Contact → Landing
```

**Kinetic-chain reasoning for this default order** (S1's entire 8-stage
model is explicitly framed around "a series of segmental rotations
involving the entire kinetic chain," proximal-to-distal, ground up — S1
abstract and throughout): the serve is a sequential summation-of-speed
motion. Each stage's output is the next stage's input:

1. **Setup** sets the base of support that **Leg drive** will later push
   against (S1, Loading section: "the back leg provides most of the
   upward and forward push, whereas the front leg provides a stable
   post"). A setup fault (e.g., abnormal stance width) constrains every
   downstream stage, so it is checked first.
2. **Toss** is the one placement decision the player makes *before*
   the fast part of the motion starts, and S4 shows elite players vary
   toss position *intentionally* by target but keep it *consistent* for
   a given target — so a toss fault (inconsistent or badly placed) is
   structurally upstream of everything else: the body has to physically
   go to wherever the ball is. A good trophy position cannot fix a bad
   toss; the arm/trunk will just compensate (S1's "premature dropping of
   the tossing arm... can lead to an exaggerated horizontal abduction,
   or arm lag," Cocking section) and S7 shows players actively use elbow
   variability *near impact* to compensate for toss variability — i.e.,
   toss errors get pushed downstream and show up as contact-point
   compensation if not fixed at the source.
3. **Trophy** (loading/cocking) converts the setup+toss position into
   stored elastic energy and the “shoulder-over-shoulder” tilt that
   generates racket height (S1, Loading section, citing ref. 48). It
   depends on 1 and 2 being adequate.
4. **Leg drive** releases the stored energy from stage 3 — S1: "effective
   leg drive forces the racket in a downward motion away from the back.
   This energy is recovered to assist in generating racket velocity
   during the acceleration phase" (Cocking section) — so leg drive is
   graded *after* trophy because its own quality is partly determined by
   how well stage 3 set it up.
5. **Contact** is the culmination of 1-4; S2/S3's MER and impact figures
   show contact quality (elbow/shoulder angles, trunk tilt) is a direct
   readout of everything upstream, which is why it is fixed last rather
   than first even though it's the most visible "result."
6. **Landing** is a consequence of weight transfer decisions made during
   leg drive and is graded last because fixing it in isolation ("land
   further forward") without fixing leg drive usually just produces a
   forced, unnatural finish.

**Exceptions a coach would make to this order** (standard coaching
practice reasoning; I could not find a primary citation specifically
ranking exception-handling in the sources fetched this session — this
sub-section is flagged as coach-consensus/pattern-matching from the
literature's own causal language, not a directly quoted priority rule):

- **If the player "arms" the serve (visibly no leg drive / near-straight
  knees at the deepest-bend event) even though their toss and trophy
  position look acceptable, fix leg drive before toss.** Rationale: S1
  states beginner servers show "greater vertical and horizontal force
  production and earlier activation of the major lower body muscle" is
  what separates them from elite servers (citing ref. 32) — a totally
  arm-driven motion is a bigger ball-speed and injury-risk problem than
  a few centimetres of toss drift, and a toss fix is wasted effort if
  the leg drive is going to be rebuilt next anyway.
- **If toss-apex position variance across repeated serves is huge
  (e.g., toss offset bounces around far outside the player's own
  consistency band from row 2), fix toss before anything else**,
  including an otherwise-passable trophy/leg-drive. Rationale: S4 shows
  elite players' toss position is *reproducible* for a given target —
  large inconsistency is itself the primary fault signature of a
  beginner/intermediate server, and S7 shows players compensate for
  toss variability with late elbow adjustments, meaning an inconsistent
  toss will keep generating *different* downstream "faults" each serve,
  making every other checkpoint unreliable to grade until toss is
  stabilized.
- **If a shoulder-pain/impingement-risk pattern is suspected (e.g.,
  toss consistently too close to the head / 12 o'clock position, S1
  Release section), flag and prioritize that over a pure performance
  fix**, since S1 directly links this toss pattern to subacromial
  impingement risk — an injury-prevention exception that overrides the
  performance-ordered tree.

---

## 3. Cannot-see list

| Item | Why 2D body pose can't support it | What the system should say instead |
|---|---|---|
| **Grip** (Continental/Eastern/Western) | Grip is encoded in hand/finger/racket-handle orientation; COCO-17 has a single wrist keypoint and no racket keypoints at all, so there is no signal for how the hand is wrapped around the handle. | "I can't see your grip from this video. If your serve feels like a slap or you can't get spin, have a coach check your grip in person." |
| **Pronation** (forearm rotation through contact) | This is an internal-rotation/forearm-roll motion largely invisible even in 3D marker sets without wrist/forearm markers, and categorically invisible on a single 2D wrist point with no hand orientation; S1/S2/S3's own shoulder/elbow rotation numbers (e.g., 172° external rotation) were measured with dedicated 3D motion capture (20+ cameras), not 2D pose. | "I can only see your overall arm swing, not the forearm roll at the very end — that's something a coach needs to check up close or in 3D." |
| **Racket-face angle at contact** | No racket keypoints exist in the model at all; face angle requires tracking the racket head/frame, not the hand. | "I'm not tracking your racket, so I can't tell you about your racket face angle at contact." |
| **Internal shoulder rotation (speed/ROM)** | S2 measured shoulder internal rotation angular velocity up to ~2420°/s (males) using high-speed 3D capture of the upper arm's long axis — this kind of fast, small-amplitude rotation about the humeral long axis is not resolvable from a single 2D elbow-wrist line at consumer frame rates, and 2D projection cannot separate internal rotation from other arm motions anyway. | "Internal shoulder rotation happens too fast and too subtly for this kind of video to measure — that's a 3D/lab-only metric." |
| **Wrist snap** | Related to pronation/ulnar-radial deviation and racket-head acceleration at the very last instant before and through contact; again requires racket + hand-orientation tracking, not a single wrist point, and typically occurs within a few milliseconds that a 2D RGB video at normal slow-mo frame rates (120-240fps) still under-samples relative to the ~1950°/s wrist flexion velocities reported in S2. | "I can't isolate the wrist snap itself — I can only show you the bigger arm and racket-path pattern around it." |
| **"Stiffness" / tension (e.g., collapsing tossing arm mentioned in S8)** | Tension is a muscular/proprioceptive quality, not a position; pose estimation only gives joint *positions* per frame, not muscle activation (S1 cites EMG studies throughout for exactly this reason — EMG is a separate sensing modality entirely). | "I can see your arm position but not how relaxed or tense it is — that's a feel-based coaching cue, not something I can measure." |
| **Ball spin** | Spin requires tracking the ball's surface markings/seams frame-to-frame at high resolution, or a dedicated spin sensor; a colour-blob toss-detector (as specified for this system) only gives ball centroid position, not rotation. | "I can see where the ball went, not how much it spun." |
| **Racket drop depth** | "How deep the racket drops" (an explicit fault example in S8) requires tracking the racket head position behind the back — with no racket keypoints, the system can only infer *arm* position (e.g., elbow/wrist height), which is a weak and indirect proxy at best. | "I can't see your racket, so I can't measure how deep your backswing drop is — only your arm position, which isn't the same thing." |
| **Ball speed** | Requires either radar/Doppler (as used in S2/S3's own 183/149 km/h figures, "recorded from the stadium radar gun") or frame-accurate ball tracking with a calibrated court-scale reference; a colour-filter toss detector built for a slow, near-vertical toss is not a validated horizontal ball-flight tracker, and consumer phone video frame rates plus motion blur on a fast serve make speed estimation unreliable without dedicated calibration. | "I'm not set up to measure ball speed accurately from this video." |

---

## 4. Key-position definitions (frozen comparison frames)

### Trophy
**Operational definition proposed for this system**: the frame in the
interval [toss-apex event, ball-contact event] at which the **hitting
wrist keypoint reaches its highest point before beginning its final
downward/forward acceleration toward contact** (i.e., the local maximum
of wrist height prior to the forward swing). This approximates S1's
"Cocking" stage (stage 4), which S1 describes as occurring just before
the Acceleration stage, at maximal shoulder external rotation — S1/S2
report MER occurs **0.090±0.014 s before contact** (S1, citing S2), so a
reasonable additional guard is to require the chosen frame fall roughly
within that time window of the contact event once frame rate is known.

- **What fails from the side view**: mostly works — the hitting wrist's
  vertical excursion is well resolved in profile, and S1's described
  shoulder-over-shoulder tilt and front-knee flexion are both clearly
  side-view-friendly 2D angles.
- **What fails from the rear view**: the wrist can be occluded by the
  head/torso for part of the cocking motion in some players' styles
  (especially foot-back/platform stances with a deep backswing — S1),
  and the depth component of "lowest point of racket drop" (unavailable
  anyway, no racket) is invisible; shoulder-line tilt (row 5) is actually
  *better* measured from behind than from the side.
- **Fallback**: if the wrist-height local-maximum detector is noisy
  (e.g., double peaks from a hitch in the motion), fall back to a
  fixed-offset frame: contact-frame minus a constant number of frames
  corresponding to ~0.09 s (per S1/S2's MER timing figure) at the
  video's known frame rate, and use that as the trophy frame instead.

### Contact
**Operational definition**: the ball-contact frame as given directly by
the audio-onset event — no additional derivation needed from pose data,
since this event is provided by the system's audio pipeline.

- **What fails from the side view**: essentially nothing structural —
  this is the brief's own stated primary/preferred view, and S2/S4's
  contact-related numbers (trunk tilt 48°, arm abduction 101°,
  contact-x shifting by target) are all consistent with a side-view
  read, with the caveat that very fast arm/racket motion can cause
  motion-blur-driven keypoint jitter exactly at this frame regardless of
  camera angle.
- **What fails from the rear view**: horizontal depth-into-court
  position of contact (row 8) is not resolvable; only left-right contact
  position and vertical height (row 9) remain usable.
- **Fallback**: if the audio onset is ambiguous (e.g., off-court noise,
  double-bounce echo) or clearly inconsistent with the pose data (e.g.,
  flagged racket-arm not near full extension at that frame), fall back
  to the frame where the hitting-wrist keypoint reaches its overall
  **maximum height** in the clip, since S1/S2 both describe contact as
  occurring near peak reach with the arm still slightly flexed
  (S2: "the elbow, wrist, and lead knee were slightly flexed" at
  impact) rather than at a fully straight-arm frame, which is a useful
  distinguishing detail if multiple high-wrist frames are candidates.

### Landing
**Operational definition**: the first frame after the contact event at
which the front-foot ankle keypoint's vertical pixel coordinate (y)
**stops decreasing** (i.e., the foot has finished descending and planted)
— as given directly in the brief. This is consistent with S1's
description of landing as the point where "large horizontal braking
forces are developed with the front foot" (Loading section) — i.e., a
genuine foot-plant/deceleration event, not merely "feet back on the
ground" for a server who never fully leaves the ground.

- **What fails from the side view**: works well for vertical
  (descending) motion and for identifying a monotonic landing, but
  judging foot-fault / baseline-relative position requires a calibrated
  court line in frame, which a side-on, player-filling-the-frame shot
  (as specified) is unlikely to have reliably.
- **What fails from the rear view**: left/right foot identity and
  whether the *back* foot also lands (full-stance info) are actually
  easier from behind; front-to-back baseline distance is equally hard
  from either single, uncalibrated camera angle.
- **Fallback**: if both ankles are moving (player hops or shuffles after
  contact — common on big first serves), take the **first local y-minimum
  after contact for the front ankle specifically** (not simply "y stops
  decreasing," which can be ambiguous with a stepping/hopping
  follow-through) rather than waiting for full stillness, since full
  stillness may be several frames later and would misrepresent the
  actual landing event S1 associates with braking force generation.

---

## 5. Common amateur fault ranking (baseline "always guess this first")

I was not able to retrieve a single peer-reviewed or named-coaching-channel
survey this session that explicitly ranks fault *frequency* with a cited
number (e.g., "60% of amateurs do X") — Brave/DuckDuckGo/Bing searches for
this specific claim were blocked or rate-limited before I could confirm
one. The ranking below is built by triangulating (a) which faults the
fetched primary sources identify as the ones that cause the largest
downstream/compensatory effects (i.e., most load-bearing in the kinetic
chain, and thus most likely to be visibly "the" problem when a serve
looks off), and (b) the well-documented, frequently-repeated coaching
narrative pattern across popular instructional content (Feel Tennis,
S8, directly verified; Top Tennis Training/Essential Tennis/Intuitive
Tennis/Tennis Evolution/2MinuteTennis content described from general
knowledge of these channels, **not re-verified live this session** —
flagged per the brief's instruction to flag inferences explicitly).

1. **Toss inconsistency / toss too far behind the head or body.**
   Source basis: S1 (Release section) explicitly names toss location as
   a driver of arm-abduction/impingement risk and a known cause of
   compensatory arm-lag (S1, Cocking section, "premature dropping of the
   tossing arm, coupled with early hip and trunk forward rotation");
   S4 shows pros keep toss position *tight* per target, implying
   inconsistency is the amateur-vs-pro discriminator; S8 (feeltennis.net,
   live-verified) frames a low/inconsistent toss as the root cause behind
   a cascade of other visible symptoms in its own worked example.
   **Flag**: frequency ranking itself (i.e., that this is specifically
   "#1 most common") is coach-consensus/pattern-inference by me, not a
   literature-stated statistic.
2. **Little to no leg drive / knees staying nearly straight through
   loading ("arming" the serve).**
   Source basis: S1 directly contrasts "beginner servers" against elite
   servers on exactly this axis (earlier/greater lower-body force
   production in elite servers, citing ref. 32); S3 shows even *elite*
   players vary meaningfully in knee flexion (7.6° vs 14.7°), so amateurs
   with even less flexion than the "low" elite group are a very plausible
   common pattern. **Flag**: frequency claim is my inference.
3. **Contact point too far in front of or behind the body relative to
   target (mistimed reach), often from toss drift propagating forward.**
   Source basis: downstream consequence per the row 2/row 8 root-cause
   chains above (S1, S4). **Flag**: named as commonly reported by
   coaching channels from general knowledge, not independently verified
   this session.
4. **Insufficient shoulder-over-shoulder tilt / "flat" trophy position**
   (hitting shoulder not dropped below the non-hitting shoulder).
   Source basis: S1 directly states this tilt is "a feature of powerful
   servers," implying its absence is a feature of less powerful/amateur
   servers (S1, Loading section). **Flag**: frequency ranking is my
   inference.
5. **Landing/finish collapse — stopping the motion at contact instead of
   continuing forward momentum into the court (poor weight transfer).**
   Source basis: S1 frames landing-stage braking forces and eccentric
   demand as a trained quality that develops with proper technique
   (Loading section); a server who doesn't drive forward won't produce
   this pattern, which is commonly described in coaching content
   (general knowledge, **not independently verified live this session**)
   as a common amateur tell.

---

## 6. Cross-check against the Djokovic 3D repo stat

The repository's own 3D-broadcast-lifting stat for Djokovic at the
deepest-knee-bend frame — **left knee 102.4° included angle (95-108°,
10th-90th percentile), right knee 117.7° (104-126°)** — sits squarely
inside the "100-120°" band the brief quotes as a general literature
figure, but I want to be precise about what I could and could not confirm
this session: the fetched primary sources (S1/S2/S3) give **front-knee
flexion-from-standing** figures (e.g., S3's 7.6° vs 14.7° *change* during
the backswing; S1's ">15° recommended" *change* threshold) rather than an
absolute included angle at the single deepest-bend instant, so they are
not directly comparable numbers to the repo's 102-118° *included-angle*
stat — they describe a different quantity (delta vs. absolute angle) at
possibly a different instant in the motion (end of backswing vs. true
deepest bend, which S1/S3's "end position" language suggests may be the
same instant, but this is not stated unambiguously in the text I could
retrieve). Taking the repo's two numbers at face value: a **right-knee
(rear/back leg in a right-handed server's typical stance) angle of
117.7°** is more flexed (smaller included angle = more bent) than a
"nearly straight ~160-170°" leg would be, consistent with S1's
description of substantial rear-knee loading and its reported rear-knee
extension *range* (foot-up 59.4°, foot-back 44.8°) implying the rear
knee starts quite bent and then extends through the stage — plausible
agreement in direction, not a verified number match. The **left-knee
(front/lead leg) 102.4°** figure is at the more-flexed end of the quoted
100-120° band; S1's explicit, directly-read threshold is a much looser
">15° of flexion from standing" for the front knee, which a 102.4°
included angle would clearly satisfy if standing full extension is
~170-180° included angle, but again this is an inference bridging two
different units of measurement (delta-degrees-from-standing vs.
absolute included angle), not a literature-stated equivalence. **Bottom
line**: the repo's Djokovic numbers are broadly plausible and in the
right neighbourhood versus what the Sydney-2000-dataset papers (S1/S2/S3)
describe qualitatively and in a different metric, but I could not
locate a primary source in this session reporting the Djokovic figure's
exact quantity (absolute included angle at deepest bend, separately for
front vs. back knee) for a true apples-to-apples validation — treat the
100-120° band as a reasonable sanity-check range rather than a
peer-reviewed target, and prefer the repo's own percentile bands
(10th-90th) as the actual pass/fail reference for an elite-level
comparison, since those came from the same measurement methodology the
system will presumably reuse.

---

## Gaps and uncertainties (explicit)

- **ITF Coaching & Sport Science Review**: I attempted to reach
  itfcoachingreview.com directly; it returned HTTP 403 to the automated
  fetch, and general search engines did not surface a specific,
  citable article with hard numbers in the time available. No content
  from this source is used above beyond the brief's own framing.
- **USTA technique checklists**: I did not find and fetch a specific,
  citable USTA document this session (searches were blocked/rate
  limited); all "coach consensus" items above should be understood as
  my own reasoned fallback per the brief's instructions, not a verified
  USTA citation.
- **Named coaching YouTube channels (Top Tennis Training, Intuitive
  Tennis, Tennis Evolution, 2MinuteTennis)**: toptennistraining.com's
  domain appears to be parked/expired (resolved to a domain-marketplace
  page during this session); I could not fetch a live page from any of
  these four channels this session. Only Feel Tennis (feeltennis.net,
  S8) was successfully fetched and read. Any cues/drills attributed in
  spirit to the other channels above are general, well-established
  instructional patterns from public knowledge of these channels'
  content, explicitly flagged as not re-verified live, per instructions.
- **Kovacs & Ellenbecker 2011 stages 5-8**: the live fetch of the PMC
  full text consistently rendered only the Preparation-phase narrative
  (stages 1-4); Acceleration/Contact/Deceleration/Follow-through
  (stages 5-8) body text was not retrievable as readable markdown in
  this session despite repeated attempts (including a raw-HTML fetch).
  Everything attributed to S1 above about stages 5-8 is inferred from
  the abstract, figure captions, and stage-4 text's forward references
  (e.g., "stage 6" contact mentioned inside the stage-3 paragraph),
  not from reading stage 5-8's own paragraphs directly — flagged
  wherever used.
- **Contact height ≈1.5× standing height** and **front-knee 100-120°
  at deepest bend** (both from the brief's own prompt) could not be
  traced to a specific number inside S1-S8; both are labelled "coach
  consensus, no primary citation located this session" above, per the
  brief's own fallback instruction for this situation.
- **Hip-shoulder separation ("X-factor") and stance-width/landing
  distance-from-baseline numeric bands**: no 2D-camera-measurable
  numeric band was found in any fetched source; all three are presented
  above as self-referential (player-vs-own-history) pass rules rather
  than universal literature bands, which I believe is the honest
  option given the literature gap, but it is a design choice worth the
  team re-examining if a better source turns up (suggested follow-up:
  try fetching the ITF Coaching & Sport Science Review via a
  non-automated browser/cache, or source Tennis Australia's own public
  coaching resources, which host some of S4-S7's findings in
  practitioner-facing form).
- **Search tooling constraints**: Google/Bing/DuckDuckGo search endpoints
  returned irrelevant or blocked content throughout this session; Brave
  Search worked briefly then rate-limited (HTTP 429) for the remainder
  of the session. PubMed/PMC's E-utilities API and direct PMC article
  pages were the reliable channel used for essentially all literature
  citations above. If better search access is available in a follow-up
  session, prioritize re-attempting: (1) ITF Coaching & Sport Science
  Review full-text search, (2) a named frequency-ranked amateur-fault
  survey, (3) S1's stages 5-8 full text via an alternate mirror or the
  publisher's PDF.
