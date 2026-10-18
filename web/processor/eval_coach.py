"""Run actual Ventuno generations against locally reviewed development clips.

Run from the repository root. No model mocks and no cached generations. Expected
labels and manual review notes are not sent to the model. This measures deterministic practice selection plus approved-cue phrasing,
not independent visual tennis diagnosis.
"""
import argparse,json,time,hashlib
from pathlib import Path
from commentary import MODEL,VERSION,PROMPT,coaching_candidates,coaching_request,model_request,parse_coach_reply,video_quality,analyse_video

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cases',type=Path,default=Path(__file__).with_name('fixtures')/'coaching_eval.json')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--repeat',type=int,default=1);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.cases.read_text());installed=next(m for m in model_request('tags')['models'] if m['name']==MODEL)
    rows=[]
    for case in manifest['cases']:
        result=json.loads(Path(case['result']).read_text()) if case.get('result') else {}
        quality=video_quality(case['video']);candidates=coaching_candidates(result,quality)
        for repeat in range(args.repeat):
            payload=coaching_request(candidates);started=time.monotonic()
            gated=candidates[0]['focus_id']=='recapture'
            if gated:
                raw=None;parsed=analyse_video(Path(case['video']),result);accepted=parsed['model_status']=='insufficient_evidence'
            else:
                raw=model_request('chat',payload);parsed=parse_coach_reply(raw.get('message',{}).get('content',''),candidates)
                accepted=parsed is not None and raw.get('model')==MODEL and raw.get('done_reason')=='stop'
            elapsed=round(time.monotonic()-started,2)
            row={'id':case['id'],'repeat':repeat,'model_called':not gated,'video_sha256':hashlib.sha256(Path(case['video']).read_bytes()).hexdigest(),'latency_seconds':elapsed,'quality':quality,'accepted':accepted,
                 'focus_id':parsed['focus_id'] if parsed else None,'expected_focus':case['expected_supported_focus'],
                 'pass':accepted and parsed['focus_id']==case['expected_supported_focus'],
                 'has_practice_coverage':accepted and parsed['focus_id']!='recapture','parsed':parsed}
            rows.append(row)
            (args.out/f"{case['id']}-{repeat}.json").write_text(json.dumps({'version':VERSION,'model':installed,'prompt':PROMPT,'request':payload,'raw':raw,'evaluation':row},indent=2))
            print(json.dumps({k:row[k] for k in ['id','repeat','latency_seconds','accepted','focus_id','pass']}),flush=True)
    summary={'version':VERSION,'model':installed,'cases':len(manifest['cases']),'generations':sum(r['model_called'] for r in rows),'passed':sum(r['pass'] for r in rows),
             'note':manifest['note'],'rows':rows}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2))
    raise SystemExit(0 if all(r['pass'] for r in rows) else 1)

if __name__=='__main__':main()
