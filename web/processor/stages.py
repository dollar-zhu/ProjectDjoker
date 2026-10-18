"""Conservative body-motion intervals, not the paper's ball/racket event detector.

All times are video playback timestamps. Tracking scores are not probabilities.
Missing joints/gaps abstain per stage; no interpolation across occlusions.
"""
import numpy as np
from compare2d.serve2d import smooth
from dms.contract import interior_angles

VERSION='body-stages-v1'
STAGES=[('setup','Setup'),('toss','Tossing-arm rise'),('loading','Loading'),
        ('acceleration','Upward swing / reach'),('follow_through','Follow-through'),('finish','Finish / recovery')]


def movement_stages(times,pose,load,reach,offset=0):
    t=np.asarray(times,float);p=np.asarray(pose,float);n=len(t)
    output={key:{'id':key,'label':label,'status':'unavailable','time':None,'frame':None,
                 'start':None,'end':None,'detail':'Not enough visible movement to identify this stage.',
                 'evidence':[],'method':VERSION} for key,label in STAGES}
    if load is None or reach is None or not 0<=load<reach<n:
        return list(output.values())
    torso=np.linalg.norm(p[:,[5,6]].mean(1)-p[:,[11,12]].mean(1),axis=1)
    finite=torso[np.isfinite(torso)&(torso>0)]
    if not len(finite): return list(output.values())
    scale=float(np.median(finite))
    s=smooth(t,p);angles=interior_angles(p)
    # Never let smoothing turn a missing joint into observed evidence.
    s[~np.isfinite(p)]=np.nan
    shoulders=s[:,[5,6]].mean(1)
    wrist=(shoulders[:,1]-s[:,10,1])/scale
    toss=(shoulders[:,1]-s[:,9,1])/scale
    max_gap=max(.12,1.6*float(np.median(np.diff(t))))

    def visible(a,b,joints):
        return (b>=a and np.isfinite(p[a:b+1,joints]).all()
                and (b==a or np.max(np.diff(t[a:b+1]))<=max_gap))

    def emit(key,a,b,at,detail,observation,cue,measurements):
        output[key].update(status='estimated',time=float(t[at]),frame=int(at+offset),
                           start=float(t[a]),end=float(t[b]),detail=detail,
                           evidence=[{'id':key,'observation':observation,'cue':cue,'measurements':measurements}])

    # A visible rise is observable without claiming ball release or toss apex.
    before=np.flatnonzero((t>=t[load]-2.5)&(t<=t[load]+.5*(t[reach]-t[load]))&np.isfinite(toss))
    toss_start=None
    best=None
    for b in before:
        earlier=before[(before<b)&(t[before]>=t[b]-1.5)]
        earlier=np.array([a for a in earlier if visible(a,b,[5,6,9])],dtype=int)
        if not len(earlier): continue
        a=int(earlier[np.argmin(toss[earlier])])
        rise=toss[b]-toss[a]
        if rise>=.4 and toss[b]>=.3 and t[b]-t[a]>=.1 and visible(a,b,[5,6,9]):
            if best is None or rise>best[0]: best=(float(rise),a,int(b))
    if best:
        rise,a,b=best
        # Trim an idle prefix to the beginning of the visible rise.
        moving=np.flatnonzero(toss[a:b+1]>toss[a]+.08)
        a=max(a,a+int(moving[0])-1) if len(moving) else a
        toss_start=a
        emit('toss',a,b,b,'Estimated tossing-arm rise. Ball release and toss apex are not measured.',
             'The tossing wrist rises above shoulder level during preparation in this view.',
             'Replay the arm rise into loading and check how the two movements overlap.',
             {'wrist_rise_torso_lengths':round(rise,2)})

    # Stable setup must precede the arm rise (or loading if rise is unavailable).
    setup_end=toss_start if toss_start is not None else load
    for b in range(setup_end,-1,-1):
        a=int(np.searchsorted(t,t[b]-.25))
        if t[b]-t[a]<.2 or not visible(a,b,[5,6,11,12,15,16]): continue
        if np.max(np.ptp(s[a:b+1,[5,6,11,12,15,16]],axis=0))/scale>.1: continue
        width=float(np.linalg.norm(p[b,15]-p[b,16])/scale)
        emit('setup',a,b,b,'A relatively still body position before the serve movement; not a stance-quality score.',
             'A relatively still setup is visible before the upward movement.',
             'Use this frame as your starting position when replaying the complete sequence.',
             {'ankle_spacing_torso_lengths':round(width,2)})
        break

    left,right=angles[load,2:4]
    a=max(0,int(np.searchsorted(t,t[load]-.2)));b=min(reach,int(np.searchsorted(t,t[load]+.1)))
    emit('loading',a,b,load,'Deepest tracked knee bend before upward reach; not a verified trophy position.',
         f'At loading, the left knee angle is {left:.0f}° and the right is {right:.0f}° in this view.',
         'Replay loading into the upward swing and watch the knees begin to straighten.',
         {'left_knee_deg':round(float(left),1),'right_knee_deg':round(float(right),1)})

    # Report visible joint positions, not racket acceleration or contact.
    if visible(load,reach,[5,6,11,12,13,14,15,16]):
        change=float(np.mean(angles[reach,2:4])-np.mean(angles[load,2:4]))
        direction='straighter' if change>=0 else 'more bent'
        detail='Body-motion interval ending at highest hitting wrist. Contact and racket speed are not measured.'
        if not visible(load,reach,[10]): detail+=' Arm tracking is incomplete within this interval; the observation uses leg positions at the endpoints.'
        emit('acceleration',load,reach,reach,detail,
             f'The knees are {abs(change):.0f}° {direction} on average at upward reach than at loading in this view.',
             'Replay this interval slowly and watch the timing of leg extension and the hitting-arm rise.',
             {'mean_knee_change_deg':round(change,1),'playback_duration_s':round(float(t[reach]-t[load]),3)})
    else:
        output['acceleration']['detail']='Loading and reach are visible, but intervening tracking is incomplete. Their timing does not establish the swing path.'

    follow_end=None
    for b in range(reach+1,n):
        if t[b]-t[reach]>2: break
        if not visible(reach,b,[5,6,10]): break
        if wrist[reach]-wrist[b]>=.4 and wrist[b]<.5 and t[b]-t[reach]>=.08:
            follow_end=b
            drop=float(wrist[reach]-wrist[b])
            emit('follow_through',reach,b,b,'Visible hitting-arm descent after reach. Does not measure deceleration forces or pronation.',
                 'The hitting wrist lowers after the overhead reach in the visible follow-through.',
                 'Replay the downward arm path and watch whether tracking follows the arm throughout.',
                 {'wrist_descent_torso_lengths':round(drop,2)})
            break
    if follow_end is not None:
        for a in range(follow_end+1,n):
            b=int(np.searchsorted(t,t[a]+.3))
            if b>=n: break
            if not visible(a,b,[5,6,10,11,12,15,16]): continue
            movement=float(np.max(np.ptp(s[a:b+1,[5,6,10,11,12,15,16]],axis=0))/scale)
            if movement>.12: continue
            emit('finish',a,b,a,'Relatively settled body and arm after follow-through. Landing and foot-ground contact are not established.',
                 'A relatively settled recovery position is visible after the arm lowers.',
                 'Review the recovery position and feet at the end of the movement.',
                 {'visible_motion_torso_lengths':round(movement,2)})
            break
    return list(output.values())
