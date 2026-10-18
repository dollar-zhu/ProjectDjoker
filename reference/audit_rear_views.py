"""Rebuild the derived rear-view inclusion manifests without modifying source poses.
Run from the repository root with a Python environment containing NumPy.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web/processor'))
from rear_view import rear_view,MIN_COHERENCE

for folder in ('reference','sinner'):
    base=ROOT/folder/'results';source=base/'aligned_trajectories.npz'
    records=[]
    with np.load(source,allow_pickle=False) as data:
        for name,pose in zip(data['filenames'].tolist(),data['aligned_poses']):
            rear,info=rear_view(pose)
            records.append({'filename':name,'included':rear is not None,**info})
    included=sum(r['included'] for r in records)
    result={'source':'aligned_trajectories.npz','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'sourceCount':len(records),'includedCount':included,'excludedCount':len(records)-included,
            'method':'One rigid rotation from mean unit hip axis at phases 85..100; rear-view assumption after upward reach.',
            'minimumCoherence':MIN_COHERENCE,'sourceCameraView':'unknown',
            'limitation':'Derived rear projections, not a verified subset of original rear-camera recordings.',
            'records':records}
    (base/'rear_view_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'{folder}: {included}/{len(records)} eligible; {len(records)-included} excluded')
