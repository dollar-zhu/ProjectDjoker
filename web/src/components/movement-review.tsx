'use client';
import {useEffect,useRef,useState} from 'react';
import type {Stage} from '@/lib/playback';
export type Analysis={focus_id:string|null;stage_id?:string|null;title:string;observation:string;rationale:string;cue:string;drill:string;success_check:string;limitation:string;source:string;model_status:string;note?:string;evidence_times:number[]};

export function CoachFeedback({analysis:a,onSeek,onSelect}:{analysis:Analysis;onSeek?:(time:number)=>void;onSelect?:(id:string)=>void}){
 const status=a.model_status==='completed'?'YOUR PRACTICE PLAN':a.model_status==='insufficient_evidence'?'A CLEARER RECORDING':'REVIEWED PRACTICE CARD';
 return <div className="coach-feedback">
  <span className="pill">{status}</span><h3>{a.title}</h3>
  <p className="observation">{a.observation}</p><p>{a.rationale}</p>
  <p className="practice-cue"><strong>{a.cue}</strong></p>
  <h4>Try this</h4><p>{a.drill}</p><h4>What to check</h4><p>{a.success_check}</p>
  {a.evidence_times.length>0&&<div className="coach-evidence"><span>Evidence frames </span>{a.evidence_times.map(t=><button key={t} className="text-button" onClick={()=>{onSeek?.(t);if(a.stage_id)onSelect?.(a.stage_id);}} disabled={!onSeek}>View {t.toFixed(2)}s</button>)}</div>}
  <p className="small muted">{a.limitation}</p><small>{a.source}</small>
  {!['completed','insufficient_evidence'].includes(a.model_status)&&<p role="status">{a.model_status==='busy'?'Gemma 4 is busy.':a.model_status==='reply_rejected'?'The model response did not pass the feedback checks.':'Gemma 4 is unavailable.'} Showing the reviewed fallback; you can try again.</p>}
 </div>;
}

export function MovementTimeline({stages,active,onReplay,onSelect}:{stages:Stage[];active:string;onReplay:(s:Stage)=>void;onSelect:(id:string)=>void}){
 const selected=stages.find(s=>s.id===active)||stages.find(s=>s.id==='loading')||stages[0];
 return <div className="moments"><div className="section-label">YOUR SERVE SEQUENCE <span>ESTIMATED BODY MOVEMENT</span></div>
  <div className="movement-grid">{stages.map((s,i)=><button key={s.id} className={`moment ${selected?.id===s.id?'active':''} ${s.status==='unavailable'?'unavailable':''}`} onClick={()=>{onSelect(s.id);if(s.status==='estimated')onReplay(s);}}><span className="moment-number">0{i+1}</span><span><strong>{s.label}</strong><small>{s.time===null?'Couldn’t identify':`${s.start!.toFixed(2)}–${s.end!.toFixed(2)}s · 0.25×`}</small></span><span>{s.time===null?'?':'▶'}</span></button>)}</div>
  {selected&&<p className="moment-detail">{selected.detail}</p>}
  <details className="technical"><summary>How this relates to the eight-stage serve</summary><p>Start → setup; release → tossing-arm rise; loading → knee bend; acceleration/contact → upward swing and reach; deceleration → visible follow-through; finish → recovery. Cocking/racket drop, ball release and contact remain unmeasured. Body stages can overlap.</p><p>These are experimental estimates from a single camera. Missing stages mean insufficient evidence, not a technique fault. <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC3445225/" target="_blank" rel="noreferrer">Eight-stage framework ↗</a></p></details>
 </div>;
}

export function MovementInsight({jobId,stages,active,onReplay,onSelect,onSeek}:{jobId:string;stages:Stage[];active:string;onReplay:(s:Stage)=>void;onSelect:(id:string)=>void;onSeek?:(time:number)=>void}){
 const request=useRef<AbortController|null>(null);
 useEffect(()=>()=>request.current?.abort(),[]);
 const [analysis,setAnalysis]=useState<Analysis|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const stage=stages.find(s=>s.id===active)||stages.find(s=>s.id==='loading')||stages[0];
 const observation=stage?.evidence[0];
 async function analyse(){
  request.current?.abort();const controller=new AbortController();request.current=controller;setBusy(true);setError('');
  try{const r=await fetch('/api/commentary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId}),signal:controller.signal});const d=await r.json();if(!r.ok)throw Error(d.error);if(!controller.signal.aborted){setAnalysis(d);if(d.stage_id&&stages.some(s=>s.id===d.stage_id))onSelect(d.stage_id);}}
  catch(e){if(!controller.signal.aborted)setError((e as Error).message);}finally{if(!controller.signal.aborted)setBusy(false);}
 }
 return <div className="movement-insight">
  <div className="gemma-review"><span className="eyebrow">ONE FOCUS FOR YOUR NEXT REP</span>
   <p>Your tracked movement selects a practice card. Gemma 4 on Ventuno phrases its approved cue; the drill and check stay unchanged.</p>
   <button className="primary" disabled={busy} onClick={analyse}>{busy?'Gemma 4 is preparing your practice plan…':analysis?'Review again with Gemma 4':'Get coaching with Gemma 4'}</button>
   <div aria-live="polite">{error&&<p role="alert" className="error">{error}</p>}{analysis&&<CoachFeedback analysis={analysis} onSeek={onSeek} onSelect={onSelect}/>}</div>
  </div>
  {stage&&<details className="technical"><summary>Tracked movement: {stage.label}</summary><p>{observation?.observation||stage.detail}</p>
   {observation&&<button className="text-button" onClick={()=>onReplay(stage)}>Replay this stage · 0.25×</button>}
  </details>}
 </div>;
}
