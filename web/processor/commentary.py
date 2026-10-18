"""Gemma 4 coaching on Ventuno, grounded in stored body-movement evidence.

The app selects a supported practice card; the board phrases its approved cue
using main's shared v3 voice prompt. Cards retain the drill and success check.
"""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from coaching.board_feedback import COACH_PROMPTS, coach_request, validate

VERSION='gemma4-ventuno-main-v3'
MODEL='gemma4:e2b'
CARDS=json.loads(Path(__file__).with_name('coaching_cards.json').read_text())
PROMPT=COACH_PROMPTS['v3'][0].format(max_words=55)
LIMITATION='Body tracking does not establish ball contact, toss placement or shot outcome. This is a practice focus, not a diagnosed fault.'


def prepare_evidence(raw):
    if raw.get('player') not in ['Novak Djokovic','Jannik Sinner']: raise ValueError('Unknown player')
    keys=['time','userLeft','userRight','referenceLeft','referenceRight']
    if any(type(raw.get(k)) not in (int,float) or not math.isfinite(raw[k]) for k in keys): raise ValueError('Invalid evidence')
    if not 0<raw['time']<20 or any(not 0<=raw[k]<=180 for k in keys[1:]): raise ValueError('Evidence outside supported range')
    return {**{k:raw[k] for k in ['player',*keys]},'direction':'review',
            'observation':f"Compare your loading position with {raw['player']}. A difference in knee angle does not establish a technique fault.",
            'cue':'Follow the bend into the upward movement; do not try to copy an exact professional knee angle.'}


def generate(raw):
    return {**prepare_evidence(raw),'source':'Measured comparison · reviewed guidance','model_status':'not_requested',
            'note':'Use the coaching review for a practice plan. The professional overlay describes similarity, not serve quality.'}


def video_quality(path):
    """Conservative repeated-frame gate, not a general video-quality classifier.

    More than 90% near-identical consecutive frames cannot support our timing
    feedback. Genuine extreme slow motion may also require a better source.
    """
    import cv2
    import numpy as np
    cap=cv2.VideoCapture(str(path));previous=None;duplicates=0;pairs=0
    try:
        fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not fps or not math.isfinite(fps) or not .5<=count/fps<=20.1: return {'status':'unreadable'}
        for _ in range(min(int(count),2400)):
            ok,frame=cap.read()
            if not ok:break
            gray=cv2.cvtColor(cv2.resize(frame,(256,192)),cv2.COLOR_BGR2GRAY).astype(float)
            if previous is not None:
                duplicates+=float(np.mean(np.abs(gray-previous)))<.02;pairs+=1
            previous=gray
        if pairs<5:return {'status':'unreadable'}
        fraction=duplicates/pairs
        return {'status':'repeated_frames' if fraction>.9 else 'usable','duplicate_fraction':round(fraction,4)}
    finally:cap.release()


def coaching_candidates(result,quality=None):
    stages={s['id']:s for s in result.get('stages',[]) if s.get('status')=='estimated' and s.get('evidence')}
    candidates=[]
    def add(focus,observation,stage=None,limitation=LIMITATION):
        times=sorted({stage[k] for k in ['start','end'] if type(stage.get(k)) in (int,float) and math.isfinite(stage[k]) and 0<=stage[k]<=20.1}) if stage else []
        candidates.append({**CARDS[focus],'focus_id':focus,'observation':observation,'limitation':limitation,'evidence_times':times})
    if quality and quality['status']!='usable':
        add('recapture','Most frames repeat almost unchanged, so the movement timing cannot be assessed.' if quality['status']=='repeated_frames' else 'The recording could not be decoded well enough to review the movement.',limitation='This source does not support a reliable movement sequence; no technique correction is justified.')
        return candidates
    acceleration=stages.get('acceleration',{});change=acceleration.get('evidence',[{}])[0].get('measurements',{}).get('mean_knee_change_deg')
    if type(change) in (int,float) and math.isfinite(change) and change>5:
        add('rhythm','Your knees move from a bent position toward straighter legs as you rise into the overhead motion.',acceleration)
    if 'follow_through' in stages:
        add('recovery','Your hitting arm comes down after the overhead reach as your body moves into recovery.',stages['follow_through'])
    if 'toss' in stages:
        add('preparation','Your non-hitting arm rises during preparation for the overhead motion.',stages['toss'])
    if not candidates:
        add('recapture','There is not enough reliable tracked movement to choose a technique focus.',limitation='Missing tracking does not mean bad technique. A clearer uninterrupted recording is needed.')
    return candidates


def approved_feedback(selected):
    return {'canonical_text':selected['cue'],'cue_speech':selected['cue'],
            'suggestion':selected['cue'],'observation':selected['observation'],
            'praise':None,'praise_speech':None,'rating':None,'allowed_numbers':[],
            'max_words':55}


def parse_coach_reply(reply,candidates):
    try:
        d=json.loads(reply)
        if not isinstance(d,dict) or set(d)!={'speech'} or not isinstance(d['speech'],str):return None
        if not candidates or candidates[0]['focus_id']=='recapture':return None
        selected=candidates[0]
        checked=validate(approved_feedback(selected),reply,coach=True)
        if not checked['accepted']:return None
        return {**selected,'cue':checked['speech'],'rationale':selected['purpose'],
                'note':selected['limitation'],'version':VERSION,'evidence_kind':'stored_body_tracking'}
    except (ValueError,TypeError,KeyError):return None


def model_request(route,payload=None,timeout=120):
    """Execute loopback HTTP ON the board through ADB. No Mac/cloud fallback."""
    if route not in ('tags','chat'):raise ValueError('Unsupported model route')
    args=['curl','--fail','--silent','--show-error','--max-time',str(timeout),'-H','Content-Type: application/json']
    if payload is not None:args+=['--data-binary','@-']
    args+=['http://127.0.0.1:11434/api/'+route]
    p=subprocess.run(['adb','-s',os.environ.get('DJOKER_SERIAL','242692658'),'shell',shlex.join(args)],
                     input='' if payload is None else json.dumps(payload),capture_output=True,text=True,timeout=timeout+5)
    if p.returncode or len(p.stdout)>2*1024*1024:raise OSError('Ventuno model request failed')
    return json.loads(p.stdout)


def fallback_plan(result,quality=None):
    selected=coaching_candidates(result,quality)[0]
    return {**selected,'rationale':'Use this small practice task, then compare the next recording.',
            'note':selected['limitation'],'evidence_kind':'measured_fallback','source':'Reviewed practice card · fallback',
            'model_status':'unavailable','version':VERSION}


def coaching_request(candidates):
    # Keep main's prompt/examples and approved-cue contract, with board transport.
    request=coach_request(approved_feedback(candidates[0]),MODEL)
    return {'model':MODEL,'stream':False,'think':False,'format':'json','keep_alive':'10m',
            'messages':request['messages'],
            'options':{'temperature':request['temperature'],'seed':42,'num_ctx':4096,
                       'num_predict':request['max_tokens'],'num_thread':4,'num_gpu':0}}


def analyse_video(path,result):
    model=os.environ.get('DJOKER_GEMMA_MODEL',MODEL)
    if model!=MODEL:return {**fallback_plan(result),'model_status':'unsupported_model'}
    quality=video_quality(path);candidates=coaching_candidates(result,quality);fallback=fallback_plan(result,quality)
    if candidates[0]['focus_id']=='recapture':
        return {**fallback,'model_status':'insufficient_evidence','source':'Recording review · more evidence needed','rationale':CARDS['recapture']['purpose']}
    base=Path(os.environ.get('DJOKER_DATA_DIR',ROOT/'local/web-jobs')).parent/'commentary';base.mkdir(parents=True,exist_ok=True)
    try:
        with (base/'gemma4-ventuno.lock').open('w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return {**fallback,'model_status':'busy'}
            installed=next((m for m in model_request('tags',timeout=5).get('models',[]) if m.get('name')==MODEL),None)
            if not installed:return fallback
            fingerprint={'version':VERSION,'model':MODEL,'digest':installed['digest'],'video':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                         'candidates':candidates,'quality':quality,'request':coaching_request(candidates)}
            key=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest();cache=base/(key+'.json')
            if cache.exists():return {**json.loads(cache.read_text()),'cached':True}
            started=time.monotonic();raw=model_request('chat',coaching_request(candidates))
            parsed=parse_coach_reply(raw.get('message',{}).get('content',''),candidates);latency=round(time.monotonic()-started,2)
            accepted=parsed is not None and raw.get('done_reason')=='stop' and raw.get('model')==MODEL
            (base/(key+'.audit.json')).write_text(json.dumps({'fingerprint':fingerprint,'response':raw,'accepted':accepted,'latency_seconds':latency},indent=2))
            if not accepted:return {**fallback,'model_status':'reply_rejected'}
            parsed.update(source='Gemma 4 E2B · Ventuno CPU · reviewed practice content',model_status='completed',model=MODEL,
                          model_digest=installed['digest'],latency_seconds=latency,cached=False)
            temporary=cache.with_suffix('.tmp');temporary.write_text(json.dumps(parsed,allow_nan=False));temporary.replace(cache)
            return parsed
    except (OSError,ValueError,KeyError,TimeoutError,subprocess.TimeoutExpired):return fallback


if __name__=='__main__':
    if len(sys.argv)==2:
        path=Path(sys.argv[1]);result=json.loads(path.read_text())
        print(json.dumps(analyse_video(path.with_name('video.mp4'),result),allow_nan=False))
    else:print(json.dumps(generate(json.loads(sys.stdin.read())),allow_nan=False))
