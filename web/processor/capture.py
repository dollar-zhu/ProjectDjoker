"""Timestamp-based capture gates, not a validated serve/contact classifier.

A single player must fill the selected area. RTMPose is a top-down pose model,
not a person/identity detector. Sustained visible joints gate presence.
"""
import math
import numpy as np


class ServeCapture:
    def __init__(self):
        self.state = 'waiting'
        self.present_since = self.overhead_since = self.lowered_since = self.lost_since = None
        self.started = self.cooldown_until = 0
        self.saw_overhead = False
        self.last_t = self.last_lowered = None
        self.lowered_observed = 0
        self.was_lowered = False

    def reset_finish(self):
        self.lowered_since = self.last_lowered = None
        self.lowered_observed = 0
        self.was_lowered = False

    def update(self, t, present, overhead, lowered):
        dt=0 if self.last_t is None else t-self.last_t
        self.last_t=t
        if dt>.5+1e-9:
            self.reset_finish()
            self.overhead_since=None
            self.saw_overhead=False
        if self.state == 'cooldown':
            if t < self.cooldown_until:
                return None
            self.state = 'waiting'
        if self.state == 'waiting':
            if not present:
                self.present_since = None
            elif self.present_since is None:
                self.present_since = t
            elif t - self.present_since >= .5:
                self.state = 'recording'
                self.started = t
                self.saw_overhead = False
                self.overhead_since = self.lowered_since = self.lost_since = None
                self.reset_finish()
                return 'start'
            return None
        event = None
        # Short unknown intervals pause evidence accumulation; they do not
        # erase an otherwise observed follow-through. Never finish while blind.
        if self.last_lowered is not None and not self.was_lowered and t-self.last_lowered>.25:
            self.reset_finish()
        if not present:
            self.overhead_since = None
            self.was_lowered=False
            if self.lost_since is None:
                self.lost_since = t
            if t - self.lost_since >= 1:
                event = 'discard'
        else:
            self.lost_since = None
            if overhead:
                self.reset_finish()
                if self.overhead_since is None:
                    self.overhead_since = t
                if t - self.overhead_since >= .06:
                    self.saw_overhead = True
            else:
                self.overhead_since = None
            if self.saw_overhead and lowered:
                if self.lowered_since is None:
                    self.lowered_since = t
                if self.was_lowered:
                    self.lowered_observed+=dt
                self.last_lowered=t
                self.was_lowered=True
                if t-self.lowered_since>=.8-1e-9 and self.lowered_observed>=.5-1e-9 and t-self.started>=1:
                    event = 'complete'
            elif not lowered:
                self.was_lowered=False
        if t - self.started >= 18:
            event = 'discard'
        if event:
            self.state = 'cooldown'
            self.cooldown_until = t + 2
            self.present_since = None
        return event


def motion_features(pose, handedness='right'):
    """Use only observed torso/arm joints; pose has NaNs for low confidence."""
    p = np.asarray(pose, float)
    visible = np.isfinite(p).all(axis=1)
    body = [5, 6, 11, 12]
    lengths = [np.linalg.norm(p[a] - p[b]) for a, b in [(5, 11), (6, 12)]
               if visible[a] and visible[b]]
    if sum(visible[body]) < 3 or not lengths:
        return None
    scale = float(np.median(lengths))
    if scale <= 1e-6:
        return None
    shoulder, elbow, wrist = (6, 8, 10) if handedness == 'right' else (5, 7, 9)
    def height(joint):
        if not visible[shoulder] or not visible[joint]:
            return None
        return float((p[shoulder, 1] - p[joint, 1]) / scale)
    return {'wrist': height(wrist), 'elbow': height(elbow),
            'body': p[body].copy(), 'scale': scale}


class MotionFinish:
    """Observed reach → arm descent → recovery, tolerating missing wrists.

    Elbow descent must be corroborated by visible torso movement. Missing
    joints never contribute displacement or observed duration. This identifies
    a body-motion sequence, not racket contact or biomechanical correctness.
    """
    def __init__(self, handedness='right'):
        self.handedness = handedness
        self.last_t = self.last_body = self.overhead_since = None
        self.saw_overhead = False
        self.peak_wrist = self.peak_elbow = float('-inf')
        self.anchor = None
        self.anchor_scale = None
        self.lowered_since = self.last_lowered = None
        self.observed = 0
        self.was_lowered = False
        self.follow_time = self.finish_time = None
        self.evidence = {}

    def update(self, t, pose):
        if self.finish_time is not None:
            return None
        dt = 0 if self.last_t is None else t - self.last_t
        if dt > .5 + 1e-9 or (self.last_body is not None and t-self.last_body > .5+1e-9):
            self.__init__(self.handedness)
            dt = 0
        self.last_t = t
        features = motion_features(pose, self.handedness)
        if features is None:
            self.was_lowered = False
            self.overhead_since = None
            return None
        self.last_body = t
        wrist, elbow = features['wrist'], features['elbow']
        overhead = ((wrist is not None and wrist >= .5)
                    or (wrist is None and elbow is not None and elbow >= .25))
        if overhead:
            if self.overhead_since is None:
                self.overhead_since = t
            if wrist is not None and wrist > self.peak_wrist:
                self.peak_wrist = wrist
                self.anchor, self.anchor_scale = features['body'], features['scale']
            if elbow is not None and elbow > self.peak_elbow:
                self.peak_elbow = elbow
                if self.anchor is None:
                    self.anchor, self.anchor_scale = features['body'], features['scale']
            # Two consecutive 20/30 fps observations establish a brief reach;
            # a lone peak cannot satisfy a positive observed interval.
            if t-self.overhead_since >= .03-1e-9:
                self.saw_overhead = True
            self.lowered_since = self.last_lowered = None
            self.observed = 0
            self.was_lowered = False
            return None
        self.overhead_since = None
        if not self.saw_overhead or self.anchor is None:
            return None
        common = np.isfinite(self.anchor).all(1) & np.isfinite(features['body']).all(1)
        shift = (float(np.max(np.linalg.norm(features['body'][common]-self.anchor[common], axis=1)))
                 / self.anchor_scale) if common.sum() >= 2 else 0
        wrist_down = (wrist is not None and self.peak_wrist >= .5
                      and self.peak_wrist-wrist >= .4 and wrist < .1)
        elbow_down = (elbow is not None and self.peak_elbow >= .2
                      and self.peak_elbow-elbow >= .35 and elbow < -.1
                      and (wrist is None or wrist < .5) and shift >= .08)
        lowered = wrist_down or elbow_down
        if self.last_lowered is not None and t-self.last_lowered > .5+1e-9:
            self.lowered_since = None
            self.observed = 0
        if not lowered:
            self.was_lowered = False
            return None
        if self.lowered_since is None:
            self.lowered_since = t
        if self.was_lowered:
            self.observed += dt
        self.was_lowered = True
        self.last_lowered = t
        self.evidence = {'body_recovery_shift_torso_lengths': round(shift, 3),
                         'observed_descent_seconds': round(self.observed, 3)}
        if wrist_down:
            self.evidence['wrist_descent_torso_lengths'] = round(self.peak_wrist-wrist, 3)
        if elbow_down:
            self.evidence['elbow_descent_torso_lengths'] = round(self.peak_elbow-elbow, 3)
        if self.follow_time is None and self.observed >= .1-1e-9:
            self.follow_time = t
            return 'descent'
        if self.follow_time is not None and self.observed >= .2-1e-9 and t-self.lowered_since >= .3-1e-9:
            self.finish_time = t
            return 'complete'
        return None


class ReadyServeCapture:
    """Deliberate ready hold → countdown → independently observed serve.

    Ready evidence must be contiguous. After completion or cancellation, a
    visible released hand is required before the next cue can arm recording.
    """
    def __init__(self, handedness='right'):
        self.handedness = handedness
        self.finish = MotionFinish(handedness)
        self.motion = ServeCapture()
        self.state = 'waiting'
        self.started = 0
        self.countdown = None
        self.ready_progress = 0
        self.armed = True
        self.last_t = self.ready_since = self.release_since = None
        self.countdown_end = self.lost_since = None

    @property
    def saw_overhead(self):
        return self.finish.saw_overhead or self.motion.saw_overhead

    def cancel(self):
        self.finish = MotionFinish(self.handedness)
        self.state = 'waiting'
        self.countdown = self.countdown_end = self.ready_since = None
        self.ready_progress = 0
        self.armed = False
        self.release_since = self.lost_since = None

    def update(self, t, present, overhead, lowered, ready, pose=None):
        gap = 0 if self.last_t is None else t - self.last_t
        self.last_t = t
        if self.state == 'recording':
            if pose is None:
                event = self.motion.update(t, present, overhead, lowered)
            else:
                # Full-body visibility gates ready, but an observed torso/arm
                # sequence can finish even when ankles or the wrist occlude.
                body_visible = motion_features(pose, self.handedness) is not None
                event = self.motion.update(t, body_visible, overhead, False)
                recovery = self.finish.update(t, pose)
                if recovery == 'complete' and event != 'discard':
                    event = 'complete'
                    self.motion.state = 'cooldown'
                    self.motion.cooldown_until = t + 2
            if event:
                self.state = 'cooldown'
                self.armed = False
                self.release_since = None
            return event
        if self.state == 'cooldown':
            if t < self.motion.cooldown_until:
                return None
            self.state = 'waiting'
        if self.state == 'countdown':
            if gap > .5 + 1e-9:
                self.cancel()
                return None
            if not present:
                if self.lost_since is None:
                    self.lost_since = t
                if t - self.lost_since >= .5 - 1e-9:
                    self.cancel()
                    return None
            else:
                self.lost_since = None
            self.countdown = max(0, math.ceil(self.countdown_end - t - 1e-9))
            if t >= self.countdown_end - 1e-9 and present:
                # Never carry the ready/countdown motion into serve evidence.
                self.motion = ServeCapture()
                self.finish = MotionFinish(self.handedness)
                self.motion.state = self.state = 'recording'
                self.motion.started = self.started = t
                self.motion.last_t = t
                self.countdown = None
                self.ready_progress = 0
                return 'start'
            return None
        if not self.armed:
            if present and not ready:
                if self.release_since is None or gap > .3:
                    self.release_since = t
                if t - self.release_since >= .3 - 1e-9:
                    self.armed = True
            else:
                self.release_since = None
            return None
        if not present or not ready or gap > .3 + 1e-9:
            self.ready_since = None
            self.ready_progress = 0
        if present and ready:
            if self.ready_since is None:
                self.ready_since = t
            self.ready_progress = min(1, (t - self.ready_since) / .75)
            if self.ready_progress >= 1:
                self.state = 'countdown'
                self.countdown_end = t + 3
                self.countdown = 3
                self.armed = False
                self.lost_since = None
        return None


class ContinuousServeCapture:
    """Settled stance → observed reach → descent → recovery, repeatedly.

    No ready gesture: a settled full-body stance arms detection, and the live
    loop's pre-roll supplies setup and loading before the reach. Any overhead
    arm movement completing this sequence can be captured; it is not a serve
    or contact classifier, and review applies its own evidence gates.
    """
    PRE = 3.5

    def __init__(self, handedness='right'):
        self.handedness = handedness
        self.finish = MotionFinish(handedness)
        self.state = 'waiting'
        self.started = self.cooldown_until = 0
        self.onset = self.settled_from = None
        self.last_t = self.settled_since = self.lost_since = None
        self.countdown = None
        self.ready_progress = 0
        self.armed = True
        self.captured = 0

    @property
    def saw_overhead(self):
        return self.state == 'recording'

    @property
    def clip_start(self):
        # Pre-roll never reaches back before the settled stance, so an earlier
        # uncaptured movement cannot become this clip's reach.
        return max(self.onset - self.PRE, self.settled_from)

    def cancel(self):
        self.finish = MotionFinish(self.handedness)
        self.state = 'waiting'
        self.settled_since = self.lost_since = None

    def end(self, t, event):
        self.cancel()
        self.state = 'cooldown'
        self.cooldown_until = t + 1.5
        if event == 'complete':
            self.captured += 1
        return event

    def update(self, t, present, overhead, pose):
        gap = 0 if self.last_t is None else t - self.last_t
        self.last_t = t
        if gap > .5 + 1e-9:
            event = 'discard' if self.state == 'recording' else None
            self.cancel()
            return event
        if self.state == 'cooldown':
            if t < self.cooldown_until:
                return None
            self.state = 'waiting'
        if self.state == 'recording':
            body_visible = motion_features(pose, self.handedness) is not None
            if body_visible:
                self.lost_since = None
            elif self.lost_since is None:
                self.lost_since = t
            recovery = self.finish.update(t, pose)
            if recovery == 'complete':
                return self.end(t, 'complete')
            # A serve's reach-to-recovery lasts about a second; a held raised
            # arm or wandering movement is released rather than recorded.
            held = (self.finish.overhead_since is not None
                    and t - self.finish.overhead_since >= 2 - 1e-9)
            if held or t - self.started >= 4 - 1e-9 or (self.lost_since is not None and t - self.lost_since >= 1 - 1e-9):
                return self.end(t, 'discard')
            return None
        if self.state == 'waiting':
            # Arming needs a whole, still-unraised body; walk-ins, ready holds
            # and the tail of a previous attempt cannot supply overhead evidence.
            # A single low-confidence frame pauses, rather than restarts, settling.
            if present:
                self.lost_since = None
            elif self.lost_since is None:
                self.lost_since = t
            if overhead or (self.lost_since is not None and t - self.lost_since >= .3 - 1e-9):
                self.settled_since = None
                self.ready_progress = 0
                return None
            if not present:
                return None
            if self.settled_since is None:
                self.settled_since = t
            self.ready_progress = min(1, (t - self.settled_since) / 1)
            if self.ready_progress >= 1:
                self.state = 'watching'
                self.settled_from = self.settled_since
                self.finish = MotionFinish(self.handedness)
                self.lost_since = None
            return None
        # Watching: brief ankle or wrist loss during the windup must not
        # disarm, but sustained absence returns to waiting.
        if present:
            self.lost_since = None
        elif self.lost_since is None:
            self.lost_since = t
        if self.lost_since is not None and t - self.lost_since >= 1 - 1e-9:
            self.cancel()
            self.ready_progress = 0
            return None
        self.finish.update(t, pose)
        if self.finish.saw_overhead:
            self.state = 'recording'
            self.onset = self.finish.overhead_since
            self.started = t
            self.lost_since = None
            return 'start'
        return None


def ready_pose(xy, scores, width, height):
    """Either visible wrist held near its shoulder, with the elbow below it."""
    if not pose_signal(xy, scores, width, height, 'right')[0]:
        return False
    torso = float(np.linalg.norm(xy[5:7].mean(0) - xy[11:13].mean(0)))
    for shoulder, elbow, wrist in [(5, 7, 9), (6, 8, 10)]:
        joints = xy[[elbow, wrist]]
        if (not np.isfinite(joints).all() or not np.isfinite(scores[[elbow, wrist]]).all()
                or np.any(scores[[elbow, wrist]] < .5)
                or np.any(joints < 0) or np.any(joints[:, 0] >= width)
                or np.any(joints[:, 1] >= height)):
            continue
        if (abs(xy[wrist, 1] - xy[shoulder, 1]) <= torso * .35
                and abs(xy[wrist, 0] - xy[shoulder, 0]) <= torso * .8
                and xy[elbow, 1] - xy[wrist, 1] >= torso * .25):
            return True
    return False


class PlayerCrop:
    """Follow one visible player; reacquire the full frame after sustained loss."""
    def __init__(self, operator_crop):
        self.original=list(operator_crop)
        self.box=list(operator_crop)
        self.last_seen=None

    def update(self,t,xy,present,width,height):
        if self.original!=[0,0,1,1]:
            return self.box
        if present:
            # A full-height 3:4 crop uses the model's portrait input without
            # shrinking the player to accommodate the whole landscape room.
            center=float(xy[11:13,0].mean())
            span=min(width,height*.75)
            left=max(0,min(width-span,center-span/2))
            self.box=[left/width,0,(left+span)/width,1]
            self.last_seen=t
        elif self.last_seen is None or t-self.last_seen>1:
            self.box=list(self.original)
        return self.box


def pose_signal(xy, scores, width, height, handedness):
    arm = [6,8,10] if handedness == 'right' else [5,7,9]
    required = [5,6,11,12,13,14,15,16]
    joints = xy[required]
    valid = (np.isfinite(joints).all() and np.isfinite(scores[required]).all()
             and np.all(scores[required] >= .5)
             and np.all(joints[:,0] >= 0) and np.all(joints[:,0] < width)
             and np.all(joints[:,1] >= 0) and np.all(joints[:,1] < height))
    torso = float(np.linalg.norm(xy[5:7].mean(0) - xy[11:13].mean(0)))
    present = bool(valid and torso > height * .08 and np.ptp(joints[:,1]) > height * .35)
    if not present:
        return False, False, False
    shoulder, _, wrist = arm
    # A hidden wrist is unknown motion, not a missing person. The elbow is
    # unnecessary for these wrist-height checks and often occludes in a serve.
    wrist_valid = (np.isfinite(xy[wrist]).all() and np.isfinite(scores[wrist])
                   and scores[wrist] >= .5 and 0 <= xy[wrist,0] < width
                   and 0 <= xy[wrist,1] < height)
    if not wrist_valid:
        return True, False, False
    return True, bool(xy[wrist,1] < xy[shoulder,1] - torso * .5), bool(xy[wrist,1] > xy[shoulder,1] + torso * .25)


class ManualCapture:
    """User-controlled recording; visibility never discards the clip."""
    def __init__(self):
        self.state = 'ready'
        self.started = 0
        self.finish_requested = False
        self.completion = None

    def update(self, t, command=None):
        if self.state == 'ready':
            if command == 'record':
                self.state = 'recording'
                self.started = t
                self.finish_requested = False
                self.completion = None
                return 'start'
            return None
        if command == 'finish':
            self.finish_requested = True
        if t - self.started >= 19 or (self.finish_requested and t - self.started >= .5):
            self.completion = 'manual_duration_limit' if t - self.started >= 19 else 'manual_stop'
            self.state = 'ready'
            return 'complete'
        return None
