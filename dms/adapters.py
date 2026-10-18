"""Adapters keep source provenance and refuse to promote provisional geometry."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from .definitions import MEDIAPIPE_TO_CANONICAL, LEGACY_TO_DMS_ANGLES
from .contract import base_metadata, export_canonical, write_packet, require

MEDIAPIPE_EVIDENCE='https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker#pose_landmarker_model'

def export_mediapipe_image(directory, *, landmarks, image_size, timestamps, visibility,
                           shot_id, player, handedness, camera_view, events,
                           comparison_profile_id=None):
    """Adapt already captured unmirrored MediaPipe image landmarks; no model invocation.

    image_size is (width,height) for the image coordinate frame used by landmarks.
    Caller must undo preview mirroring/cropping/letterboxing consistently before export.
    The third image-coordinate channel is deliberately dropped, never promoted to 3D.
    """
    points=np.asarray(landmarks,dtype=float)
    require(points.ndim==3 and points.shape[1]==33 and points.shape[2] in (2,3),'Expected MediaPipe image landmarks (T,33,2|3)')
    require(len(image_size)==2 and all(np.isfinite(v) and v>0 for v in image_size),'Invalid image dimensions')
    pose=points[:,MEDIAPIPE_TO_CANONICAL,:2]*np.asarray(image_size)
    if visibility is None:
        scores=np.full((len(points),17),np.nan);kind='unavailable';definition=None
    else:
        visibility=np.asarray(visibility,dtype=float);require(visibility.shape==(len(points),33),'Expected visibility (T,33)')
        scores=visibility[:,MEDIAPIPE_TO_CANONICAL];kind='tracking_score';definition='mediapipe-landmark-visibility'
    return export_canonical(directory,shot_id=shot_id,player=player,handedness=handedness,
       source={'model':'mediapipe','coordinate_system':'image_2d','camera_view':camera_view,
               'fps':None,'axis_convention':'x_right_y_down','units':'pixels','metric_space':True,
               'image_size':list(image_size),'comparison_profile_id':comparison_profile_id},
       pose=pose,timestamps=timestamps,joint_confidence=scores,confidence_kind=kind,
       score_definition=definition,mapping_evidence=MEDIAPIPE_EVIDENCE,events=events)

def export_reference(project, out):
    """Export original-index Djokovic poses + provisional angles, never canonical poses."""
    project=Path(project);out=Path(out)
    from reference.analyze import angles
    source=project/'reference/source/data';meta=pd.read_parquet(source/'metadata.parquet')
    rows=meta[meta.server.eq('Novak Djokovic')].sort_values('filename')
    require(len(rows)==88 and rows.filename.is_unique,'Expected 88 unique Djokovic metadata rows')
    records=json.loads((project/'reference/results/distribution.json').read_text())['records']
    event_rows={r['filename']:r for r in records}
    manifest={r['filename']:r for r in json.loads((project/'reference/results/manifest.json').read_text())}
    require(not out.exists() or not any(out.iterdir()),'Export root must be new or empty')
    # Validate every source hash before writing any packet.
    for r in rows.itertuples():
        require(r.filename in manifest and r.filename in event_rows,'Missing source provenance')
        require(hashlib.sha256((source/'keypoints'/r.filename).read_bytes()).hexdigest()==manifest[r.filename]['sha256'],'Reference source checksum differs')
    paths=[]
    for row in rows.itertuples():
        file=source/'keypoints'/row.filename;pose=np.load(file,allow_pickle=False).astype(float)
        require(len(pose)==row.n_frames,'Source frame count mismatch')
        features=angles(pose)[:,LEGACY_TO_DMS_ANGLES]
        shot_id=Path(row.filename).stem;n=len(pose);missing=np.full((n,17),np.nan);times=np.full(n,np.nan)
        rec=event_rows[row.filename]
        def event(frame,method,definition):
            return {'frame':int(frame),'timestamp':None,'confidence':None,'method':method,'definition_id':definition,'status':'estimated'}
        events={'max_knee_flexion':event(rec['anchors'][1],'five_frame_smoothed_bilateral_interior_angle_minimum_15_to_70_percent','djoker-knee-proxy-v1'),
                'highest_right_wrist':event(rec['anchors'][3],'five_frame_smoothed_z_maximum_after_knee','djoker-wrist-height-proxy-v1'),
                'contact':None,'racket_drop':None}
        source_info={'model':'dataset_export_motionbert_reported','coordinate_system':'unverified','camera_view':'unknown','fps':None,
                     'axis_convention':'unverified','units':'unknown','metric_space':False,'comparison_profile_id':None}
        packet=base_metadata(shot_id,'Novak Djokovic','unknown',source_info,pose,features,times,missing,events)
        packet['pose'].update(joint_schema='djoker17_unvalidated',joint_names=None,mapping_validated=False,
            mapping_evidence=None,source_layout_hypothesis='H36M; dataset author confirmation pending')
        packet['features'].update(definitions_validated=False,provenance='Recomputed with local provisional H36M triplets; equivalence to upstream angle files unverified')
        packet['timestamps']['status']='unavailable';packet['joint_confidence'].update(kind='unavailable',score_definition=None)
        packet['provenance']={'source_filename':row.filename,'source_sha256':manifest[row.filename]['sha256'],
                              'upstream_commit':'7889457cc9b50b0c2a9fdcc81d786bcdb6b8652c','quality_flags':rec['flags']}
        path=write_packet(out/shot_id,packet,dict(pose=pose,features=features,timestamps=times,joint_confidence=missing));paths.append(path)
    return paths
