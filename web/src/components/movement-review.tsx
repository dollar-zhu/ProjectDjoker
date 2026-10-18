'use client';
import {useEffect,useRef,useState} from 'react';
import type {Stage} from '@/lib/playback';
type Analysis={focus_id:string|null;observation:string;cue:string;source:string;model_status:string;note?:string};

export function MovementTimeline({stages,active,onReplay,onSelect}:{stages:Stage[];active:string;onReplay:(s:Stage)=>void;onSelect:(id:string)=>void}){
 const selected=stages.find(s=>s.id===active)||stages.find(s=>s.id==='loading')||stages[0];
 return <div className="moments"><div className="section-label">YOUR SERVE SEQUENCE <span>ESTIMATED BODY MOVEMENT</span></div>
  <div className="movement-grid">{stages.map((s,i)=><button key={s.id} className={`moment ${selected?.id===s.id?'active':''} ${s.status==='unavailable'?'unavailable':''}`} onClick={()=>{onSelect(s.id);if(s.status==='estimated')onReplay(s);}}><span className="moment-number">0{i+1}</span><span><strong>{s.label}</strong><small>{s.time===null?'Couldn’t identify':`${s.start!.toFixed(2)}–${s.end!.toFixed(2)}s · 0.25×`}</small></span><span>{s.time===null?'?':'▶'}</span></button>)}</div>
  {selected&&<p className="moment-detail">{selected.detail}</p>}
  <details className="technical"><summary>How this relates to the eight-stage serve</summary><p>Start → setup; release → tossing-arm rise; loading → knee bend; acceleration/contact → upward swing and reach; deceleration → visible follow-through; finish → recovery. Cocking/racket drop, ball release and contact remain unmeasured. Body stages can overlap.</p><p>These are experimental estimates from a single camera. Missing stages mean insufficient evidence, not a technique fault. <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC3445225/" target="_blank" rel="noreferrer">Eight-stage framework ↗</a></p></details>
 </div>;
}

export function MovementInsight({jobId,stages,active,onReplay,onSelect}:{jobId:string;stages:Stage[];active:string;onReplay:(s:Stage)=>void;onSelect:(id:string)=>void}){
 const request=useRef<AbortController|null>(null);
 useEffect(()=>()=>request.current?.abort(),[]);
 const [analysis,setAnalysis]=useState<Analysis|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const stage=stages.find(s=>s.id===active)||stages.find(s=>s.id==='loading')||stages[0];
 const observation=stage?.evidence[0];
 async function analyse(){
  request.current?.abort();const controller=new AbortController();request.current=controller;setBusy(true);setError('');
  try{const r=await fetch('/api/commentary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId}),signal:controller.signal});const d=await r.json();if(!r.ok)throw Error(d.error);if(!controller.signal.aborted){setAnalysis(d);if(d.focus_id)onSelect(d.focus_id);}}
  catch(e){if(!controller.signal.aborted)setError((e as Error).message);}finally{if(!controller.signal.aborted)setBusy(false);}
 }
 return <div className="movement-insight">
  <span className="pill">{stage?.status==='estimated'?'OBSERVED MOVEMENT · ESTIMATED STAGE':'STAGE NOT IDENTIFIED'}</span>
  <h3>{stage?.label||'Your movement'}</h3><p className="observation">{observation?.observation||stage?.detail}</p>
  {observation&&<><p className="practice-cue">{observation.cue}</p><button className="primary" onClick={()=>onReplay(stage)}>Replay this stage · 0.25× <span>↗</span></button></>}
  <div className="gemma-review"><span className="eyebrow">REVIEW THE FULL MOVEMENT</span><p>Gemma considers the measured stages and picks one focus for your next replay.</p>
   <button className="primary" disabled={busy||!stages.some(s=>s.status==='estimated')} onClick={analyse}>{busy?'Gemma is analysing…':analysis?'Analyse again with Gemma':'Analyse with Gemma'}</button>
   <div aria-live="polite">{error&&<p role="alert" className="error">{error}</p>}{analysis&&<><p className="observation">{analysis.observation}</p><p className="practice-cue">{analysis.cue}</p><small>{analysis.source}</small>{analysis.model_status!=='completed'&&<p>{analysis.model_status==='busy'?'Gemma is busy. Showing the measured default focus; try again shortly.':analysis.model_status==='reply_rejected'?'Gemma’s reply did not match the available evidence. Showing the measured default focus.':'Gemma is unavailable. Showing the measured default focus.'}</p>}<p className="small muted">{analysis.note}</p></>}</div>
  </div>
 </div>;
}
