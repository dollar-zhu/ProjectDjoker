"""Strict interchange validation and fail-closed, event-level comparisons."""
import copy
import json
from pathlib import Path
import re
import numpy as np
from .definitions import (SCHEMA_VERSION, JOINT_SCHEMA, JOINT_NAMES, ANGLE_SCHEMA,
                          ANGLE_NAMES, ANGLE_DEFINITIONS, TRIPLETS, FORMULA)

class ContractError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise ContractError(message)

def finite_number(value):
    return type(value) in (int,float) and np.isfinite(value)

def json_safe(value):
    """JSON missing numbers are null, never nonstandard NaN/Infinity tokens."""
    if isinstance(value, np.ndarray): return json_safe(value.tolist())
    if isinstance(value, np.generic): return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value): return None
    if isinstance(value, dict): return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [json_safe(v) for v in value]
    return value

def interior_angles(pose):
    pose=np.asarray(pose,dtype=float)
    require(pose.ndim==3 and pose.shape[1]==17 and pose.shape[2] in (2,3), 'Invalid pose shape')
    result=np.full((len(pose),8),np.nan)
    for j,(a,b,c) in enumerate(TRIPLETS):
        u=pose[:,a]-pose[:,b];v=pose[:,c]-pose[:,b]
        den=np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1)
        good=np.isfinite(u).all(axis=1)&np.isfinite(v).all(axis=1)&(den>1e-10)
        result[good,j]=np.degrees(np.arccos(np.clip(np.sum(u[good]*v[good],axis=1)/den[good],-1,1)))
    return result

def validate_packet(meta, arrays):
    """Structural validity is not scientific comparability. Unknowns may be explicit."""
    require(isinstance(meta,dict),'Metadata must be an object')
    for key in ['schema_version','shot_id','shot_type','player','handedness','source','pose','features','timestamps','joint_confidence','events']:
        require(key in meta,f'Missing field: {key}')
    require(meta['schema_version']==SCHEMA_VERSION,'Unsupported schema_version')
    require(isinstance(meta['shot_id'],str) and re.fullmatch(r'[A-Za-z0-9_-]+',meta['shot_id']) is not None,'Invalid shot_id')
    require(meta['shot_type']=='serve','Only serve supported in dms-0.1')
    require(isinstance(meta['player'],str) and bool(meta['player']),'Invalid player')
    require(meta['handedness'] in ('left','right','unknown'),'Invalid handedness')
    source=meta['source'];pdesc=meta['pose'];fdesc=meta['features'];tdesc=meta['timestamps'];cdesc=meta['joint_confidence']
    require(all(isinstance(v,dict) for v in (source,pdesc,fdesc,tdesc,cdesc,meta['events'])),'Invalid metadata object')
    for key in ['model','coordinate_system','camera_view','fps','axis_convention','units','metric_space']:
        require(key in source,f'Missing source.{key}')
    for key in ['model','coordinate_system','camera_view','axis_convention','units']:
        require(isinstance(source[key],str) and bool(source[key]),f'Invalid source.{key}')
    require(type(source['metric_space']) is bool,'Invalid metric_space')
    require(source['fps'] is None or (finite_number(source['fps']) and source['fps']>0),'fps must be positive or null')
    for key in ['pose','features','timestamps','joint_confidence']:
        desc=meta[key]
        require(key in arrays,f'Missing tensor: {key}')
        arr=np.asarray(arrays[key]);require(arr.dtype.kind=='f',f'{key} must use floating point for NaN support')
        require(not np.isinf(arr).any(),f'{key} contains infinity')
        require(desc.get('shape')==list(arr.shape),f'{key} declared shape does not match tensor')
        require(isinstance(desc.get('file'),str) and bool(desc['file']),f'Missing {key}.file')
        require(Path(desc['file']).name==desc['file'] and desc['file'].endswith('.npy'),f'{key}.file must be a local NPY basename')
    require(len({meta[k]['file'] for k in ['pose','features','timestamps','joint_confidence']})==4,'Tensor filenames must be distinct')
    profile=source.get('comparison_profile_id')
    require(profile is None or (isinstance(profile,str) and bool(profile.strip())),'Invalid comparison_profile_id')
    pose,features,times,confidence=(np.asarray(arrays[k]) for k in ['pose','features','timestamps','joint_confidence'])
    require(pose.ndim==3 and pose.shape[1]==17 and pose.shape[2] in (2,3) and len(pose)>0,'Expected pose (T,17,2|3)')
    n=len(pose);require(features.shape==(n,8),'Expected angles (T,8)');require(times.shape==(n,),'Expected timestamps (T,)');require(confidence.shape==(n,17),'Expected confidence (T,17)')
    require(type(pdesc.get('mapping_validated')) is bool,'Missing mapping_validated flag')
    if pdesc.get('joint_schema')==JOINT_SCHEMA:
        require(pdesc['mapping_validated'] is True,'Do not label unvalidated poses canonical17')
        require(pdesc.get('joint_names')==JOINT_NAMES,'Canonical anatomical joint order differs')
        require(isinstance(pdesc.get('mapping_evidence'),str) and bool(pdesc['mapping_evidence'].strip()),'Mapping evidence required')
    else:
        require(pdesc.get('joint_schema')=='djoker17_unvalidated' and pdesc['mapping_validated'] is False,'Unknown source joint schema')
        require(pdesc.get('joint_names') is None,'Do not assert unvalidated source joint names')
    require(fdesc.get('angle_schema')==ANGLE_SCHEMA and fdesc.get('names')==ANGLE_NAMES,'Angle schema/order mismatch')
    require(fdesc.get('definitions')==ANGLE_DEFINITIONS and fdesc.get('formula')==FORMULA,'Angle definitions mismatch')
    require(fdesc.get('units')=='degrees','Angle units must be degrees')
    require(type(fdesc.get('definitions_validated')) is bool,'Missing definitions_validated')
    require(not fdesc['definitions_validated'] or pdesc['mapping_validated'],'Cannot validate anatomical features without validated mapping')
    if pdesc['mapping_validated']:
        require(source['coordinate_system'] in (('image_2d',) if pose.shape[2]==2 else ('world_3d','camera_3d','model_3d')),'Coordinate system/dimensionality mismatch')
    require(fdesc.get('representation')==('projected_2d' if pose.shape[2]==2 else 'estimated_3d'),'Representation/dimensionality mismatch')
    finite=features[np.isfinite(features)];require(np.all((finite>=0)&(finite<=180)),'Interior angles outside [0,180]')
    if pdesc['mapping_validated'] and fdesc['definitions_validated']:
        require(source['metric_space'],'Angles require isotropic metric coordinates (e.g. image pixels, not raw normalized xy)')
        actual=interior_angles(pose)
        # Missing features may be intentionally withheld; finite supplied values must agree with the pose.
        supplied=np.isfinite(features)
        require(np.all(np.isfinite(actual[supplied])) and np.allclose(features[supplied],actual[supplied],atol=1e-3,rtol=0),'Features disagree with specified pose/triplets')
    require(tdesc.get('units')=='seconds','Timestamps must be seconds')
    require(tdesc.get('status') in ('observed','unavailable'),'Unknown timestamp status')
    if tdesc['status']=='observed':
        require(np.isfinite(times).all() and abs(times[0])<1e-8 and np.all(np.diff(times)>0),'Observed timestamps must start at zero and strictly increase')
    else:
        require(np.isnan(times).all(),'Unavailable timestamps must be NaN')
        require(source['fps'] is None,'Unknown timestamps must not claim a verified fps')
    require(cdesc.get('kind') in ('tracking_score','availability','unavailable'),'Invalid confidence kind')
    valid=confidence[np.isfinite(confidence)];require(np.all((valid>=0)&(valid<=1)),'Confidence outside [0,1]')
    if cdesc['kind']=='unavailable':require(np.isnan(confidence).all(),'Unavailable confidence must be NaN')
    if cdesc['kind']=='availability':require(np.all(np.isin(valid,[0.,1.])),'Availability must be binary')
    if cdesc['kind']=='tracking_score':require(isinstance(cdesc.get('score_definition'),str) and bool(cdesc['score_definition']),'Tracking score definition required')
    for name,event in meta['events'].items():
        if event is None: continue
        require(isinstance(event,dict),f'Invalid event {name}')
        for key in ['frame','timestamp','confidence','method','definition_id','status']:
            require(key in event,f'Missing {name}.{key}')
        frame=event['frame'];ts=event['timestamp'];score=event['confidence']
        require(frame is None or (type(frame) is int and 0<=frame<n),f'Invalid event frame: {name}')
        require(ts is None or (finite_number(ts) and ts>=0),f'Invalid event timestamp: {name}')
        require(frame is not None or ts is not None,f'Event needs frame or timestamp: {name}')
        require(score is None or (finite_number(score) and 0<=score<=1),f'Invalid event confidence: {name}')
        require(event['status'] in ('estimated','validated'),f'Invalid event status: {name}')
        require(all(isinstance(event[k],str) and bool(event[k]) for k in ['method','definition_id']),f'Invalid event definition: {name}')
        if ts is not None:
            require(tdesc['status']=='observed' and ts<=times[-1],f'Event timestamp lacks observed timeline: {name}')
            if frame is not None:require(abs(times[frame]-ts)<1e-6,f'Event frame/timestamp disagree: {name}')
    return {'valid':True,'frames':n,'mapping_validated':pdesc['mapping_validated']}

def write_packet(directory,meta,arrays):
    directory=Path(directory);validate_packet(meta,arrays)
    require(not directory.exists() or not any(directory.iterdir()),'Output directory must be new or empty')
    directory.mkdir(parents=True,exist_ok=True)
    for key,array in arrays.items():np.save(directory/meta[key]['file'],np.asarray(array),allow_pickle=False)
    path=directory/(meta['shot_id']+'.json');path.write_text(json.dumps(json_safe(meta),indent=2,allow_nan=False)+'\n')
    return path

def load_packet(path):
    path=Path(path);base=path.parent.resolve()
    def bad_number(token): raise ContractError(f'Nonstandard JSON number: {token}')
    meta=json.loads(path.read_text(),parse_constant=bad_number);arrays={}
    require(isinstance(meta,dict),'Metadata must be an object')
    for key in ['pose','features','timestamps','joint_confidence']:
        name=meta.get(key,{}).get('file');require(isinstance(name,str),'Missing tensor filename')
        file=(base/name).resolve();require(file.is_relative_to(base),'Tensor path escapes packet directory')
        arrays[key]=np.load(file,allow_pickle=False)
    validate_packet(meta,arrays)
    return meta,arrays

def base_metadata(shot_id,player,handedness,source,pose,features,times,confidence,events):
    return {'schema_version':SCHEMA_VERSION,'shot_id':shot_id,'shot_type':'serve','player':player,'handedness':handedness,
       'source':copy.deepcopy(source),
       'pose':{'joint_schema':JOINT_SCHEMA,'joint_names':JOINT_NAMES.copy(),'mapping_validated':True,'shape':list(pose.shape),'file':shot_id+'_pose.npy'},
       'features':{'angle_schema':ANGLE_SCHEMA,'names':ANGLE_NAMES.copy(),'definitions':copy.deepcopy(ANGLE_DEFINITIONS),'formula':FORMULA,'units':'degrees',
          'definitions_validated':True,'representation':'projected_2d' if pose.shape[2]==2 else 'estimated_3d','shape':list(features.shape),'file':shot_id+'_angles.npy'},
       'timestamps':{'status':'observed','units':'seconds','shape':list(times.shape),'file':shot_id+'_timestamps.npy'},
       'joint_confidence':{'kind':'tracking_score','shape':list(confidence.shape),'file':shot_id+'_confidence.npy'},'events':copy.deepcopy(events)}

def export_canonical(directory, *, shot_id, player, handedness, source, pose, timestamps,
                     joint_confidence, confidence_kind, score_definition, mapping_evidence, events):
    pose=np.asarray(pose,dtype=float);times=np.asarray(timestamps,dtype=float);scores=np.asarray(joint_confidence,dtype=float)
    feats=interior_angles(pose);meta=base_metadata(shot_id,player,handedness,source,pose,feats,times,scores,events)
    meta['pose']['mapping_evidence']=mapping_evidence
    meta['joint_confidence'].update(kind=confidence_kind,score_definition=score_definition)
    return write_packet(directory,meta,dict(pose=pose,features=feats,timestamps=times,joint_confidence=scores))

def compare_event(left,right, *, event_name, metrics=('left_knee_flexion','right_knee_flexion'), min_tracking_confidence=.5, min_event_confidence=.5):
    """Compare measured values at the same validated event; never produce coaching advice."""
    reasons=[]
    try:
        for meta,arrays in [left,right]:validate_packet(meta,arrays)
    except (ContractError,KeyError,TypeError,ValueError) as exc:
        return {'comparable':False,'reason':f'Invalid packet: {exc}'}
    l,r=left[0],right[0]
    require(bool(metrics) and all(m in ANGLE_NAMES for m in metrics),'Unknown/empty comparison metrics')
    require(0<=min_tracking_confidence<=1 and 0<=min_event_confidence<=1,'Invalid confidence threshold')
    if l['features']['representation']!=r['features']['representation']:reasons.append('2D and 3D angle representations differ')
    if not all(m['pose']['mapping_validated'] and m['pose']['joint_schema']==JOINT_SCHEMA for m in [l,r]):reasons.append('Anatomical mapping is not validated')
    if not all(m['features']['definitions_validated'] for m in [l,r]):reasons.append('Anatomical angle definitions are not validated')
    if l['handedness']=='unknown' or l['handedness']!=r['handedness']:reasons.append('Handedness differs or is unknown; no automatic mirroring')
    for field in ['coordinate_system','axis_convention','units']:
        if l['source'][field]!=r['source'][field] or l['source'][field] in ('unknown','unverified'):reasons.append(f'Incompatible or unknown {field}')
    if not l['source']['metric_space'] or not r['source']['metric_space']:reasons.append('Coordinate metric compatibility is unverified')
    if not l['source'].get('comparison_profile_id') or l['source'].get('comparison_profile_id')!=r['source'].get('comparison_profile_id'):reasons.append('No shared validated camera/coordinate comparison profile')
    if l['joint_confidence'].get('score_definition')!=r['joint_confidence'].get('score_definition'):reasons.append('Tracking-score definitions differ')
    if l['source']['camera_view'] in ('unknown','unverified') or l['source']['camera_view']!=r['source']['camera_view']:reasons.append('Camera perspectives differ or are unknown')
    indices=[ANGLE_NAMES.index(m) for m in metrics];joints=sorted({j for i in indices for j in TRIPLETS[i]});frames=[]
    for label,(meta,arrays) in [('left',left),('right',right)]:
        event=meta['events'].get(event_name)
        if event is None:reasons.append(f'{label}: requested event is unavailable');continue
        if event['status']!='validated':reasons.append(f'{label}: event is estimated, not validated')
        if event['confidence'] is None or event['confidence']<min_event_confidence:reasons.append(f'{label}: inadequate event confidence')
        frame=event['frame']
        if frame is None:
            # No silent nearest-frame matching: timestamp-only events must coincide with an observed sample.
            hits=np.flatnonzero(np.isclose(arrays['timestamps'],event['timestamp'],atol=1e-6,rtol=0))
            if len(hits)!=1:reasons.append(f'{label}: event does not identify an exact frame');continue
            frame=int(hits[0])
        frames.append(frame)
        if meta['joint_confidence']['kind']!='tracking_score':reasons.append(f'{label}: tracking confidence is unavailable or only availability was supplied')
        scores=arrays['joint_confidence'][frame,joints]
        if not np.isfinite(scores).all() or np.any(scores<min_tracking_confidence):reasons.append(f'{label}: inadequate tracking confidence for selected joints')
        if not np.isfinite(arrays['features'][frame,indices]).all():reasons.append(f'{label}: selected angles are missing')
    a=l['events'].get(event_name);b=r['events'].get(event_name)
    if a and b and a['definition_id']!=b['definition_id']:reasons.append('Event definitions differ')
    if reasons:return {'comparable':False,'reason':reasons[0],'reasons':reasons}
    x=left[1]['features'][frames[0],indices];y=right[1]['features'][frames[1],indices]
    return {'comparable':True,'event':event_name,'units':'degrees','metrics':list(metrics),
            'left':x.tolist(),'right':y.tolist(),'right_minus_left':(y-x).tolist(),
            'confidence_thresholds':{'tracking':min_tracking_confidence,'event':min_event_confidence}}
