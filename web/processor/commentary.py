"""Ground a brief coaching note in measured evidence, then phrase it on Ventuno."""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
MODEL='/home/arduino/models/gemma3-1b_qcs8275_ctxt-5000/gemma3-1b_qcs8275_ctxt-5000.pte'
TOKENIZER='/home/arduino/models/gemma3-1b_qcs8275_ctxt-5000/tokenizer.json'
RUNNER='/home/arduino/git/executorch/build-x86/examples/qualcomm/oss_scripts/llama/qnn_llama_runner'

def prepare_evidence(raw):
    if raw.get('player') not in ['Novak Djokovic','Jannik Sinner']: raise ValueError('Unknown player')
    keys=['time','userLeft','userRight','referenceLeft','referenceRight']
    if any(not isinstance(raw.get(k),(int,float)) or not math.isfinite(raw[k]) for k in keys): raise ValueError('Invalid evidence')
    if not 0<raw['time']<20 or any(not 0<=raw[k]<=180 for k in keys[1:]): raise ValueError('Evidence outside supported range')
    left=raw['userLeft']-raw['referenceLeft'];right=raw['userRight']-raw['referenceRight']
    # Conservative exploratory cue; this threshold is not a validated coaching rule.
    if max(left,right)>15 and min(left,right)>=-10:
        direction='more_bend';part='both knees' if min(left,right)>15 else 'your left knee' if left>right else 'your right knee'
        observation=f"At {raw['time']:.2f}s, {part} {'appear' if part=='both knees' else 'appears'} straighter during loading than {raw['player']} in this selected view."
        cue='Try a slightly deeper knee bend during loading in a relaxed shadow serve, then compare the overlay again.'
    elif min(left,right)<-15 and max(left,right)<=10:
        direction='less_bend';part='both knees' if max(left,right)<-15 else 'your left knee' if left<right else 'your right knee'
        observation=f"At {raw['time']:.2f}s, {part} {'appear' if part=='both knees' else 'appears'} more bent during loading than {raw['player']} in this selected view."
        cue='Explore a slightly shallower knee bend during loading in a relaxed shadow serve, then compare the overlay again.'
    else:
        direction='review';observation=f"Review your loading position at {raw['time']:.2f}s alongside {raw['player']}; the knee differences do not support a single bend-direction cue."
        cue='Replay the loading position and upward reach, checking knee alignment before changing your movement.'
    return {**{k:raw[k] for k in ['player',*keys]},'direction':direction,'observation':observation,'cue':cue}

def validate_reply(text,evidence):
    t=text.lower()
    if not 5<=len(t.split())<=55 or re.search(r'\d',t): return False
    if any(word in t for word in ['injur','pain','guarantee','faster','power','spin','racket','wrist','shoulder','elbow','always','must','perfect','jump higher','weight','forward','backward','hip','feet','foot','ankle','twist','rotate']): return False
    if 'knee' not in t or not any(w in t for w in ['loading','load','bend']): return False
    if evidence['direction']=='more_bend': return any(w in t for w in ['deeper','more','increase']) and not any(w in t for w in ['straighten','shallower','less','reduce'])
    if evidence['direction']=='less_bend': return any(w in t for w in ['shallower','less','reduce']) and not any(w in t for w in ['deeper','more','increase'])
    return any(w in t for w in ['review','replay','check','compare']) and not any(w in t for w in ['deeper','shallower','straighten','increase','reduce'])

def generate(raw):
    evidence=prepare_evidence(raw)
    base=Path(os.environ.get('DJOKER_DATA_DIR',ROOT/'local/web-jobs')).parent/'commentary';base.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest();cache=base/(key+'.json')
    if cache.exists(): return json.loads(cache.read_text())
    result={**evidence,'source':'Measured comparison · template','model_status':'unavailable','note':'Experimental practice suggestion. Camera alignment and reference mapping are approximate; match the movement pattern, not exact pro angles.'}
    adb=['adb','-s',os.environ.get('DJOKER_SERIAL','242692658')]
    def run(args,timeout=10):
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-1000:])
        return p.stdout
    try:
        with (base/'gemma.lock').open('w') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                result['model_status']='busy';return result
            run(adb+['get-state'])
            board='/home/arduino/djoker-commentary/'+str(uuid.uuid4())
            prompt=('You are a concise tennis practice assistant. Measurements are experimental 2D comparisons, not a diagnosis. '
                    f"At loading, user knee angles are {evidence['userLeft']:.0f} and {evidence['userRight']:.0f} degrees; selected reference angles are {evidence['referenceLeft']:.0f} and {evidence['referenceRight']:.0f}. "
                    'Rewrite ONLY the following approved practice cue in one short sentence. Preserve the bend direction. Do not add measurements, body parts, promises or other advice. Cue: '+evidence['cue'])
            args=[RUNNER,'--model_path',MODEL,'--tokenizer_path',TOKENIZER,'--decoder_model_version','gemma3','--eval_mode','1','--seq_len','320','--temperature','0','--output_path',board+'/reply.txt','--performance_output_path',board+'/performance.txt','--prompt',prompt]
            shell='mkdir -p '+shlex.quote(board)+' && cd '+shlex.quote(board)+' && LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib" timeout 60 '+shlex.join(args)
            started=time.monotonic();log=run(adb+['shell',shell],70)
            output=run(adb+['shell','cat '+shlex.quote(board+'/reply.txt')])
            reply=output.rsplit('<start_of_turn>model',1)[-1].split('<end_of_turn>')[0].strip()
            result.update(model_status='completed',latency_seconds=round(time.monotonic()-started,2))
            if validate_reply(reply,evidence): result.update(cue=reply,source='Gemma 3 1B · Ventuno ExecuTorch QNN')
            else: result['model_status']='reply_rejected'
            (base/(key+'.log')).write_text(log+'\nMODEL OUTPUT\n'+output)
            (base/(key+'.request.json')).write_text(json.dumps(evidence,indent=2))
            cache.write_text(json.dumps(result,allow_nan=False))
    except (OSError,RuntimeError,subprocess.TimeoutExpired): pass
    return result

def stage_candidates(stages):
    """Only persisted observations can be selected; user prompts never enter this path."""
    return [{'id':s['id'],'label':s['label'],'time':s['time'],**e}
            for s in stages if s['status']=='estimated' for e in s['evidence']]


def parse_stage_reply(reply,candidates):
    try:
        # Gemma may wrap JSON in a Markdown fence. No arbitrary text is displayed.
        text=reply.strip()
        if text.startswith('```'):
            text='\n'.join(text.splitlines()[1:-1])
        value=json.loads(text)
        if not isinstance(value,dict) or set(value)!={'focus_id'}: return None
        return value['focus_id'] if value['focus_id'] in {e['id'] for e in candidates} else None
    except (ValueError,TypeError): return None


def analyse_stages(stages):
    """Gemma reviews all visible stages and selects one evidence-backed practice focus.

    Rendering uses the selected observation verbatim: the model cannot create a
    new measurement, hidden event, technique diagnosis or unsupported correction.
    """
    candidates=stage_candidates(stages)
    if not candidates:
        return {'focus_id':None,'model_status':'no_evidence','source':'Measured stages',
                'observation':'No supported movement stages are available.','cue':'Review the recording and tracking first.'}
    fallback=next((e for e in candidates if e['id']=='loading'),candidates[0])
    result={**fallback,'focus_id':fallback['id'],'model_status':'unavailable','source':'Measured stages · default focus',
            'note':'Gemma selects a review focus from measured body movement. It does not see the video or establish a technique fault.'}
    base=Path(os.environ.get('DJOKER_DATA_DIR',ROOT/'local/web-jobs')).parent/'commentary'
    base.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(json.dumps({'version':'stage-analysis-v2','stages':stages},sort_keys=True).encode()).hexdigest()
    cache=base/(key+'.json')
    if cache.exists(): return json.loads(cache.read_text())
    adb=['adb','-s',os.environ.get('DJOKER_SERIAL','242692658')]
    def run(args,timeout=10):
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-1000:])
        return p.stdout
    try:
        with (base/'gemma.lock').open('w') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                result['model_status']='busy';return result
            run(adb+['get-state'])
            choices=[{'id':e['id'],'observation':e['observation'],'measurements':e.get('measurements',{})} for e in candidates]
            prompt=('Choose one tennis video segment to replay from the available observations below. '
                    'This is a replay selection task. A partial recording is sufficient. '
                    'Prefer a segment showing the transition between movements when available. '
                    'Copy exactly one id from the list into this JSON format: {"focus_id":"chosen_id"}. '
                    'Output JSON only. Available segments: '+json.dumps(choices,separators=(',',':')))
            board='/home/arduino/djoker-commentary/'+str(uuid.uuid4())
            args=[RUNNER,'--model_path',MODEL,'--tokenizer_path',TOKENIZER,'--decoder_model_version','gemma3',
                  '--eval_mode','1','--seq_len','1400','--temperature','0','--output_path',board+'/reply.txt',
                  '--performance_output_path',board+'/performance.txt','--prompt',prompt]
            shell='mkdir -p '+shlex.quote(board)+' && cd '+shlex.quote(board)+' && LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib" timeout 60 '+shlex.join(args)
            started=time.monotonic();log=run(adb+['shell',shell],70)
            output=run(adb+['shell','cat '+shlex.quote(board+'/reply.txt')])
            reply=output.rsplit('<start_of_turn>model',1)[-1].split('<end_of_turn>')[0].strip()
            selected=parse_stage_reply(reply,candidates)
            result.update(model_status='reply_rejected',latency_seconds=round(time.monotonic()-started,2))
            if selected:
                result.update(next(e for e in candidates if e['id']==selected))
                result.update(focus_id=selected,model_status='completed',source='Gemma 3 1B · Ventuno · evidence-selected focus')
                cache.write_text(json.dumps(result,allow_nan=False))
            (base/(key+'.log')).write_text(log+'\nMODEL OUTPUT\n'+output)
            (base/(key+'.request.json')).write_text(json.dumps(stages,indent=2))
    except (OSError,RuntimeError,subprocess.TimeoutExpired): pass
    return result


if __name__=='__main__':
    if len(sys.argv)==2:
        # Path comes from the server's validated UUID job directory, never model text.
        data=json.loads(Path(sys.argv[1]).read_text())
        print(json.dumps(analyse_stages(data.get('stages',[])),allow_nan=False))
    else:
        print(json.dumps(generate(json.loads(sys.stdin.read())),allow_nan=False))
