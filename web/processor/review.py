"""Presentation adapter for the repository's strict coaching engine; no new fault rules."""
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dms.contract import export_canonical
from compare2d.serve2d import serve_metrics
from coaching.board_feedback import decide


def retry(reason):
    return {'events':[], 'feedback': {'mode':'retry','observation':reason,
            'suggestion':'Record one complete serve from the side or rear, with the whole player in view.',
            'drill':None,'rating':{'score':None},'reference_blocked_reasons':[],
            'uncertainty':'No technique judgement was made.'}}


def review(directory,times,pose,scores,view,handedness,image_size):
    times=np.asarray(times,float);pose=np.asarray(pose,float);scores=np.asarray(scores,float)
    if len(times)<2 or not np.isfinite(times).all() or not (np.diff(times)>0).all():
        raise ValueError('Timestamps must increase strictly.')
    if view not in ('rear','side'):
        return retry('This camera view is not supported for serve feedback yet.')
    if handedness!='right':
        return retry('The current event rules support a confirmed right-handed server. Your video is available for visual review.')
    required=[5,6,11,12,13,14,15,16]
    visible=np.isfinite(pose).all(2)&np.isfinite(scores)&(scores>=.5)
    w,h=image_size
    visible &= (pose[:,:,0]>=0)&(pose[:,:,0]<w)&(pose[:,:,1]>=0)&(pose[:,:,1]<h)
    if len(times)<15 or np.mean(visible[:,required].all(1))<.7:
        return retry('Too many shoulders or leg joints are unclear. Check the player box and camera framing.')
    if visible[:,10].sum()<5:
        return retry('The hitting wrist is not visible enough to locate upward reach.')
    masked=pose.copy();masked[~visible]=np.nan
    metrics=serve_metrics(times,masked)
    if metrics is None or metrics['flags']:
        return retry('The loading and upward-reach sequence is ambiguous or too close to the clip boundary. Include setup and follow-through.')
    load,reach=metrics['load_frame'],metrics['reach_frame']
    if not visible[load,required].all() or not visible[reach,[5,6,10,11,12]].all():
        return retry('Tracking is uncertain at a key moment. Try a clearer recording.')
    # A peak wrist in an idle clip is not a serve event.
    shoulder=masked[reach,[5,6]].mean(0);hip=masked[reach,[11,12]].mean(0)
    if masked[reach,10,1] > shoulder[1]-.25*np.linalg.norm(shoulder-hip):
        return retry('No clear overhead reach was found. Include the complete upward swing.')
    source={'model':'rtmpose-m-wholebody-qnn-fp16','coordinate_system':'image_2d',
            'camera_view':view,'fps':None,'axis_convention':'x_right_y_down','units':'pixels',
            'metric_space':True,'image_size':image_size,'comparison_profile_id':None,
            'runtime':'ExecuTorch QNN on Ventuno','crop_mode':'fixed_operator'}
    packet=export_canonical(directory/'dms',shot_id=directory.name,player='uploaded_player',handedness=handedness,
             source=source,pose=masked,timestamps=times,joint_confidence=np.where(visible,np.clip(scores,0,1),np.nan),
             confidence_kind='tracking_score',score_definition='SimCC minimum xy peak clipped to 0..1; not a probability',
             mapping_evidence='RTMPose COCO wholebody first 17 body joints; web/processor/pose.py model contract',
             events={'max_knee_flexion':None,'contact':None})
    fb=decide(packet,ROOT/'reference/projected2d/board_reference.json',ROOT/'coaching/rules.json')
    if fb['mode']=='retry': return {'events':[],'feedback':fb}
    # Avoid interpreting anatomical left/right as front/back from an oblique image.
    vals=fb['metrics']
    fb['observation']=f"At the estimated loading moment, your left knee angle is {vals['front_knee_at_load']:.0f}° and right knee angle {vals['back_knee_at_load']:.0f}° in this view."
    fb['canonical_text']=fb['observation']
    events=[{'id':'loading','label':'Loading','time':float(times[load]),'frame':int(load),
             'detail':'Estimated deepest knee bend before upward reach. Review the frame; this is not a validated trophy-position label.'},
            {'id':'reach','label':'Upward reach','time':float(times[reach]),'frame':int(reach),
             'detail':'Highest tracked hitting wrist. This does not establish ball contact.'}]
    return {'events':events,'feedback':fb}
