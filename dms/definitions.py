"""Versioned anatomical and numerical definitions. Changing order requires a new version."""
SCHEMA_VERSION = 'dms-0.1'
JOINT_SCHEMA = 'canonical17'
# COCO anatomical ordering; coordinates and model output layouts are separate concerns.
JOINT_NAMES = ['nose','left_eye','right_eye','left_ear','right_ear',
               'left_shoulder','right_shoulder','left_elbow','right_elbow',
               'left_wrist','right_wrist','left_hip','right_hip','left_knee',
               'right_knee','left_ankle','right_ankle']
ANGLE_SCHEMA = 'dms-angles-v1'
ANGLE_NAMES = ['left_elbow_flexion','right_elbow_flexion','left_knee_flexion',
               'right_knee_flexion','left_shoulder_angle','right_shoulder_angle',
               'left_hip_angle','right_hip_angle']
TRIPLETS = [(5,7,9),(6,8,10),(11,13,15),(12,14,16),
            (7,5,11),(8,6,12),(5,11,13),(6,12,14)]
FORMULA = 'degrees(arccos(clip(dot(A-B,C-B)/(norm(A-B)*norm(C-B)),-1,1)))'
ANGLE_DEFINITIONS = [dict(name=n, joints=[JOINT_NAMES[j] for j in t],
                          calculation='interior_angle', units='degrees')
                     for n,t in zip(ANGLE_NAMES,TRIPLETS)]
# MediaPipe Pose landmarks -> canonical17. Never use its image-space z as metric 3D.
MEDIAPIPE_TO_CANONICAL = [0,2,5,7,8,11,12,13,14,15,16,23,24,25,26,27,28]
# Existing local analysis order is elbows, shoulders, hips, knees.
LEGACY_TO_DMS_ANGLES = [0,1,6,7,2,3,4,5]
