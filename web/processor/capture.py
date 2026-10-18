"""Timestamp-based capture gates, not a validated serve/contact classifier.

A single player must fill the selected area. RTMPose is a top-down pose model,
not a person/identity detector. Sustained visible joints gate presence.
"""
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
