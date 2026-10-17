"""Djokovic population analysis. Source layout and phase events remain provisional."""
import argparse, hashlib, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

NAMES=['Left elbow','Right elbow','Left shoulder','Right shoulder','Left hip','Right hip','Left knee','Right knee']
# Included 3D segment angles, not clinical Euler angles or shoulder rotation.
TRIPLETS=[(11,12,13),(14,15,16),(12,11,4),(15,14,1),(11,4,5),(14,1,2),(4,5,6),(1,2,3)]
EDGES=[(0,1),(1,2),(2,3),(0,4),(4,5),(5,6),(0,7),(7,8),(8,9),(9,10),(8,11),(11,12),(12,13),(8,14),(14,15),(15,16)]
TARGET=np.array([0,40,80,100])

def smooth(a,width=5):
    padded=np.pad(a,((width//2,width//2),)+((0,0),)*(a.ndim-1),mode='edge')
    return np.stack([padded[i:i+len(a)] for i in range(width)]).mean(axis=0)

def angles(p):
    if p.ndim!=3 or p.shape[1:]!=(17,3) or len(p)<20 or not np.isfinite(p).all():
        raise ValueError('Invalid pose array')
    values=[]
    for a,b,c in TRIPLETS:
        u=p[:,a]-p[:,b];v=p[:,c]-p[:,b];den=np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1)
        if np.any(den<1e-8):raise ValueError('Degenerate segment')
        values.append(np.degrees(np.arccos(np.clip((u*v).sum(axis=1)/den,-1,1))))
    return np.stack(values,axis=1)

def events(p,a,width=5):
    """Ordered pose proxies, NOT observed trophy/racket-drop/ball-contact events."""
    n=len(p);s=smooth(a,width);z=smooth(p[:,16,2],width)
    # Restrict loading to middle 15–70% to avoid terminal landing knee flexion.
    lo=max(1,round(.15*(n-1)));hi=min(n-8,round(.70*(n-1)))
    load=lo+int(np.argmin(s[lo:hi+1,6:8].mean(axis=1)))
    # Peak wrist elevation after load; exclude last 5% for follow-through samples.
    reach_lo=load+4;reach_hi=min(n-3,round(.95*(n-1)))
    reach=reach_lo+int(np.argmax(z[reach_lo:reach_hi+1]))
    cock_lo=load+1;cock_hi=reach-1
    cock=cock_lo+int(np.argmin(s[cock_lo:cock_hi+1,1]))
    flags=[]
    if load in (lo,hi):flags.append('load_search_boundary')
    if reach in (reach_lo,reach_hi):flags.append('reach_search_boundary')
    if cock in (cock_lo,cock_hi):flags.append('cock_search_boundary')
    # Plateau ambiguity measures how many candidate frames are within 2% of vertical excursion.
    tol=max(float(np.ptp(z))*.02,1e-6)
    plateau=np.flatnonzero(z[reach_lo:reach_hi+1]>=z[reach]-tol)+reach_lo
    if len(plateau)>max(5,.10*n):flags.append('broad_reach_plateau')
    if np.max(np.abs(np.diff(a,axis=0)))>40:flags.append('angle_jump_over_40deg_per_frame')
    return np.array([0,load,cock,reach,n-1]),flags

def resample(a,anchors=None):
    source=np.linspace(0,100,len(a)) if anchors is None else np.interp(np.arange(len(a)),np.asarray(anchors)[[0,1,3,4]],TARGET)
    flat=a.reshape(len(a),-1)
    return np.stack([np.interp(np.arange(101),source,flat[:,i]) for i in range(flat.shape[1])],axis=1).reshape((101,)+a.shape[1:])

def normalize_pose(p):
    # Fixed per-serve yaw; no framewise derotation. Root-center x/y, keep vertical motion relative to initial pelvis.
    scale=float(np.median(np.linalg.norm(p[:,8]-p[:,0],axis=1)))
    if scale<1e-6:raise ValueError('Degenerate torso')
    q=p.astype(float).copy();q[:,:,:2]-=q[:,0:1,:2];q[:,:,2]-=q[0,0,2]
    hip=(p[:min(10,len(p)),1,:2]-p[:min(10,len(p)),4,:2]).mean(axis=0)
    yaw=float(np.arctan2(hip[1],hip[0]));c=np.cos(yaw);s=np.sin(yaw)
    q[:,:,:2]=q[:,:,:2]@np.array([[c,-s],[s,c]])
    return q/scale

def summarize(x):
    return {'mean':np.round(x.mean(axis=0),2).tolist(),'sd':np.round(x.std(axis=0,ddof=1) if len(x)>1 else np.zeros_like(x[0]),2).tolist(),
            'p10':np.round(np.percentile(x,10,axis=0),2).tolist(),'p90':np.round(np.percentile(x,90,axis=0),2).tolist()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=Path('../djoker'));ap.add_argument('--out',type=Path,default=Path('results'))
    ap.add_argument('--download',action='store_true');ap.add_argument('--allow-partial',action='store_true');ap.add_argument('--accept-provisional-h36m',action='store_true')
    args=ap.parse_args()
    if not args.accept_provisional_h36m:ap.error('Explicit --accept-provisional-h36m is required')
    source=args.source.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    m=pd.read_parquet(source/'data/metadata.parquet');d=m[m.server.eq('Novak Djokovic')].sort_values('filename')
    if len(d)!=88 or d.filename.duplicated().any():raise ValueError('Expected 88 unique Djokovic rows')
    lookup={x['name']:x['id'] for x in json.loads((source/'keypoints_listing.json').read_text())}
    def download(name):
        import gdown
        dest=source/'data/keypoints'/name
        if not dest.exists():
            part=dest.with_suffix('.part');gdown.download(id=lookup[name],output=str(part),quiet=True,timeout=60)
            angles(np.load(part,allow_pickle=False));part.replace(dest)
    if args.download:
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download,d.filename))
    missing=[name for name in d.filename if not (source/'data/keypoints'/name).exists()]
    (out/'availability.json').write_text(json.dumps({'expected':88,'missing':missing},indent=2))
    if missing and not args.allow_partial:raise RuntimeError(f'{len(missing)} pose files missing; no population result generated')
    records=[];phase=[];raw=[];poses=[];manifest=[];frames=[]
    for row in d.itertuples():
        file=source/'data/keypoints'/row.filename
        if not file.exists():continue
        p=np.load(file,allow_pickle=False);a=angles(p)
        if len(p)!=row.n_frames:raise ValueError(f'Frame mismatch: {row.filename}')
        anchors,flags=events(p,a)
        sensitivity=np.stack([events(p,a,w)[0] for w in [3,5,7,9]])
        uncertainty=sensitivity.max(axis=0)-sensitivity.min(axis=0)
        if uncertainty[1:4].max()>max(4,.05*len(p)):flags.append('phase_smoothing_sensitive')
        rec={'filename':row.filename,'match':row.match_id,'opponent':row.returner,'serve_number':int(row.serve_number),'frames':len(p),
             'anchors':anchors.tolist(),'anchor_spread_frames':uncertainty.tolist(),'flags':flags,'speed_kmh':int(row.speed_kmh)}
        records.append(rec);phase.append(resample(a,anchors));raw.append(resample(a));poses.append(resample(normalize_pose(p),anchors))
        for frame,values in enumerate(a):frames.append([row.filename,frame,*values])
        manifest.append({'filename':row.filename,'drive_id':lookup[row.filename],'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bytes':file.stat().st_size})
    if not records:raise RuntimeError('No available poses')
    phase=np.array(phase);raw=np.array(raw);poses=np.array(poses)
    groups={}
    for name,indices in [('All',list(range(len(records)))),('First serves',[i for i,r in enumerate(records) if r['serve_number']==1]),('Second serves',[i for i,r in enumerate(records) if r['serve_number']==2])]:
        if not indices:continue
        groups[name]={'n':len(indices),'phase':summarize(phase[indices]),'progress':summarize(raw[indices]),'pose':np.round(poses[indices].mean(axis=0),3).tolist()}
    flags={flag:sum(flag in r['flags'] for r in records) for flag in sorted({f for r in records for f in r['flags']})}
    result={'expected':88,'n':len(records),'complete':len(records)==88,'joint_names':NAMES,'triplets':TRIPLETS,'edges':EDGES,'groups':groups,'records':records,
      'flag_counts':flags,'phase_labels':['Loading','Drive & upward swing','Follow-through'],
      'event_labels':['Clip start','Deepest knee bend','Most flexed right elbow','Highest right wrist','Clip end'],
      'alignment':'Piecewise linear at clip start / knee bend / wrist height / clip end = 0/40/80/100; elbow event is diagnostic only; not elapsed time',
      'layout':'Provisional H36M; no racket/ball/contact labels; z-up inferred from exported geometry',
      'angles':np.round(phase,1).tolist()}
    (out/'distribution.json').write_text(json.dumps(result,separators=(',',':')))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    pd.DataFrame(frames,columns=['filename','frame',*NAMES]).to_csv(out/'raw_joint_angles.csv',index=False)
    pd.DataFrame([{**r,'flags':';'.join(r['flags'])} for r in records]).to_csv(out/'phase_events.csv',index=False)
    np.savez_compressed(out/'aligned_trajectories.npz',phase_angles=phase,progress_angles=raw,aligned_poses=poses,filenames=np.array([r['filename'] for r in records]))
    print(json.dumps({'analyzed':len(records),'expected':88,'frames':len(frames),'flag_counts':flags,'group_counts':{k:g['n'] for k,g in groups.items()}},indent=2))

if __name__=='__main__':main()
