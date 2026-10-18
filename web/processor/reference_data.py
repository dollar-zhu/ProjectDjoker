"""Read the committed individual reference poses; no model or media downloads."""
import csv
import json
from pathlib import Path
import sys
import numpy as np
from rear_view import rear_view

ROOT=Path(__file__).resolve().parents[2]
PLAYERS={'djokovic':('reference','Novak Djokovic'),'sinner':('sinner','Jannik Sinner')}

def reference_data(player,serve_type,selected=None):
    if player not in PLAYERS or serve_type not in (1,2): raise ValueError('Unknown reference player or serve type')
    folder,label=PLAYERS[player];base=ROOT/folder/'results'
    with (base/'phase_events.csv').open() as f: rows=list(csv.DictReader(f))
    rear_poses={};views={}
    with np.load(base/'aligned_trajectories.npz',allow_pickle=False) as data:
        for name,pose in zip(data['filenames'].tolist(),data['aligned_poses']):
            rear,info=rear_view(pose);views[name]=info
            if rear is not None: rear_poses[name]=rear
    eligible=[r for r in rows if int(r['serve_number'])==serve_type and r['filename'] in rear_poses]
    if not eligible: raise ValueError('No stable rear-view reference is available')
    if selected is None:
        # Prefer stable event estimates, then a central loading position; never synthesize a mean body.
        selected=min(eligible,key=lambda r:(sum(json.loads(r['anchor_spread_frames'])[i] for i in (1,3)),abs(json.loads(r['anchors'])[1]/int(r['frames'])-.55),r['filename']))['filename']
    if selected not in {r['filename'] for r in eligible}: raise ValueError('Serve does not belong to the selected player and serve type')
    poses=rear_poses[selected]
    if poses.shape!=(101,17,3) or not np.isfinite(poses).all(): raise ValueError('Reference pose data is invalid')
    return {'player':label,'total':len(rear_poses),'sourceTotal':len(rows),'excluded':len(rows)-len(rear_poses),'view':views[selected],'kind':'individual','selected':selected,'poses':np.round(poses,5).tolist(),
            'serves':[{'id':r['filename'],'opponent':r['opponent'],'serveNumber':int(r['serve_number']),
                       'flags':r['flags'].split(';') if r['flags'] else []} for r in eligible],
            'source':'Jason Wang et al. / Tennis Serve Analysis Dataset','license':'CC BY 4.0'}

if __name__=='__main__':
    print(json.dumps(reference_data(sys.argv[1],int(sys.argv[2]),sys.argv[3] if len(sys.argv)>3 else None),allow_nan=False))
