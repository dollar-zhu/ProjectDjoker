"""Pose-derived rear projection; this does not identify the original filming side.

Use the horizontal hip axis over phase 85..100 (after estimated upward reach).
Assume the server has turned toward the court. Keep one rigid rotation for the
whole serve; never mirror joints or rotate each frame independently.
"""
import numpy as np

MIN_COHERENCE=.9

def rear_view(poses):
    info={'view':'rear','basis':'post-reach hip axis','sourceView':'unknown'}
    if poses.shape!=(101,17,3) or not np.isfinite(poses).all():
        return None,{**info,'excluded':'invalid_pose'}
    axes=poses[85:,1,:2]-poses[85:,4,:2]
    widths=np.linalg.norm(axes,axis=1)
    if np.any(widths<.05):
        return None,{**info,'excluded':'degenerate_hip_axis'}
    direction=(axes/widths[:,None]).mean(axis=0)
    coherence=float(np.linalg.norm(direction))
    info['coherence']=round(coherence,6)
    if coherence<MIN_COHERENCE:
        return None,{**info,'excluded':'unstable_post_reach_orientation'}
    right=direction/coherence
    # Screen right follows anatomical right when looking at the server's back.
    rotation=np.array([[right[0],-right[1]],[right[1],right[0]]])
    rear=poses.copy();rear[:,:,:2]=poses[:,:,:2]@rotation
    info['rotationDegrees']=round(float(np.degrees(np.arctan2(right[1],right[0]))),3)
    return rear,info
