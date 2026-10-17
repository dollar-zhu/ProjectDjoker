"""Small deterministic dataset smoke pipeline; no learned model or coaching claims."""
import argparse, hashlib, json, os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TRIPLES = {'left_elbow':(11,12,13),'right_elbow':(14,15,16),
           'left_knee':(4,5,6),'right_knee':(1,2,3)}
EDGES = [(0,1),(1,2),(2,3),(0,4),(4,5),(5,6),(0,7),(7,8),(8,9),(9,10),(8,11),(11,12),(12,13),(8,14),(14,15),(15,16)]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fetch(data):
    import gdown
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for entry in manifest['files']:
        dest=data/entry['path']; dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            temp=dest.with_suffix(dest.suffix+'.part')
            result=gdown.download(id=entry['id'],output=str(temp),quiet=True,timeout=60)
            if not result: raise RuntimeError(f"Download failed: {entry['path']}")
            if sha(temp)!=entry['sha256']: raise ValueError(f"Source changed: {entry['path']}")
            temp.replace(dest)
        if sha(dest)!=entry['sha256']: raise ValueError(f"Checksum mismatch: {entry['path']}")

def validate_pose(p):
    if p.ndim!=3 or p.shape[1:]!=(17,3) or len(p)<2:
        raise ValueError(f'Expected (T>=2,17,3), got {p.shape}')
    if not np.isfinite(p).all(): raise ValueError('Non-finite pose coordinates')

def angle(a,b,c):
    u=a-b; v=c-b
    den=np.linalg.norm(u,axis=-1)*np.linalg.norm(v,axis=-1)
    if np.any(den<1e-10): raise ValueError('Degenerate joint segment')
    return np.degrees(np.arccos(np.clip(np.sum(u*v,axis=-1)/den,-1,1)))

def features(p):
    validate_pose(p)
    return np.stack([angle(p[:,a],p[:,b],p[:,c]) for a,b,c in TRIPLES.values()],axis=1)

def dtw(a,b):
    """Full endpoint-constrained DTW, L1 mean-angle local cost; diagnostic only."""
    n,m=len(a),len(b); cost=np.full((n+1,m+1),np.inf);cost[0,0]=0
    for i in range(1,n+1):
        for j in range(1,m+1):
            cost[i,j]=np.abs(a[i-1]-b[j-1]).mean()+min(cost[i-1,j-1],cost[i-1,j],cost[i,j-1])
    path=[];i,j=n,m
    while i and j:
        path.append((i-1,j-1))
        step=int(np.argmin([cost[i-1,j-1],cost[i-1,j],cost[i,j-1]]))
        if step==0:i-=1;j-=1
        elif step==1:i-=1
        else:j-=1
    path=np.asarray(path[::-1]);delta=np.abs(a[path[:,0]]-b[path[:,1]])
    return path,delta.mean(axis=0)

def analyze(data,out,layout):
    out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for e in manifest['files']:
        if sha(data/e['path'])!=e['sha256']:raise ValueError(f"Checksum mismatch: {e['path']}")
    m=pd.read_parquet(data/'metadata.parquet')
    required={'filename','server','match_id','n_frames','serve_number','gender','speed_kmh'}
    if not required.issubset(m.columns) or m.filename.duplicated().any():raise ValueError('Metadata schema/key failure')
    d=m[m.server.eq('Novak Djokovic')]
    report={'metadata_rows':len(m),'metadata_columns':len(m.columns),'players':m.server.nunique(),'matches':m.match_id.nunique(),
      'schema':{c:{'dtype':str(m[c].dtype),'null_count':int(m[c].isna().sum())} for c in m},
      'djokovic_serves':len(d),'djokovic_matches':d.groupby(['match_id','returner']).size().reset_index(name='serves').to_dict('records'),
      'layout':'H36M inferred from coordinates and MotionBERT; NOT confirmed by dataset author',
      'units':'Angles in degrees; coordinate physical scale and upstream velocity units unverified',
      'samples':[],'comparisons':[]}
    d.to_csv(out/'djokovic_metadata.csv',index=False)
    poses={}; fs={}
    for p in sorted((data/'keypoints').glob('*.npy')):
        rows=m[m.filename.eq(p.name)]
        if len(rows)!=1:raise ValueError(f'Unmatched sample {p.name}')
        row=rows.iloc[0];pose=np.load(p,allow_pickle=False);validate_pose(pose)
        if len(pose)!=int(row.n_frames):raise ValueError(f'Frame mismatch: {p.name}')
        f=features(pose);poses[p.name]=pose;fs[p.name]=f
        pd.DataFrame(f,columns=TRIPLES).to_csv(out/(p.stem+'_angles.csv'),index=False)
        rec={'filename':p.name,'server':row.server,'serve_number':int(row.serve_number),'speed_kmh':int(row.speed_kmh),
          'shape':list(pose.shape),'dtype':str(pose.dtype),'all_finite':bool(np.isfinite(pose).all()),
          'coordinate_min':float(pose.min()),'coordinate_max':float(pose.max()),
          'angle_ranges_degrees':{name:[float(f[:,i].min()),float(f[:,i].max())] for i,name in enumerate(TRIPLES)}}
        v=data/'angular_velocities'/p.name
        if v.exists():
            arr=np.load(v,allow_pickle=False)
            if arr.shape!=(len(pose),8) or not np.isfinite(arr).all():raise ValueError('Invalid velocity array')
            rec['upstream_velocity_shape']=list(arr.shape)
        report['samples'].append(rec)
    ref=next(s['filename'] for s in report['samples'] if s['server']=='Novak Djokovic' and s['serve_number']==1)
    for name,f in fs.items():
        if name==ref:continue
        path,err=dtw(fs[ref],f)
        np.save(out/(Path(name).stem+'_dtw_path.npy'),path)
        report['comparisons'].append({'reference':ref,'sample':name,'path_length':len(path),
            'mean_absolute_angle_gap_degrees':dict(zip(TRIPLES,map(float,err)))})
    os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for i,(name,ax) in enumerate(zip(TRIPLES,axes.flat)):
        for s in report['samples']:
            f=fs[s['filename']];ax.plot(np.linspace(0,100,len(f)),f[:,i],label=s['server']+' '+s['filename'].split('_')[1])
        ax.set(title=name.replace('_',' '),xlabel='Sequence progress (%) — not serve phase',ylabel='Angle (degrees)')
    axes[0,0].legend(fontsize=7);fig.suptitle('Sample angle trajectories · provisional H36M mapping')
    fig.savefig(out/'angle_trajectories.png',dpi=140);plt.close(fig)
    p=poses[ref];fig=plt.figure(figsize=(12,4))
    for k,idx in enumerate([0,len(p)//2,len(p)-1]):
        ax=fig.add_subplot(1,3,k+1,projection='3d')
        for a,b in EDGES:ax.plot(*p[idx,[a,b],:].T,marker='o',markersize=2)
        ax.set(xlim=(-.8,.8),ylim=(-.8,.8),zlim=(0,1.8),title=f'Frame {idx} (not a labeled phase)');ax.set_box_aspect((1.6,1.6,1.8))
    fig.suptitle('Djokovic sample · provisional H36M skeleton');fig.savefig(out/'pose_check.png',dpi=140);plt.close(fig)
    (out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ['metadata_rows','players','matches','djokovic_serves']},indent=2))
    print(f'Validated {len(poses)} poses. Results: {out}')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['fetch','analyze','run'])
    parser.add_argument('--data',type=Path,default=ROOT/'data');parser.add_argument('--out',type=Path,default=ROOT/'reports')
    parser.add_argument('--layout',choices=['h36m'],help='Explicitly accept provisional H36M interpretation')
    args=parser.parse_args()
    if args.command in ['analyze','run'] and args.layout is None:parser.error('--layout h36m required: mapping is provisional')
    if args.command in ['fetch','run']:fetch(args.data)
    if args.command in ['analyze','run']:analyze(args.data,args.out,args.layout)
