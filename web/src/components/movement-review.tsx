'use client';
import {useEffect,useRef,useState} from 'react';
import type {Stage} from '@/lib/playback';
import {bodyFocus,formatMeasurement,type BodyFocus} from '@/lib/review-focus';
import {loadCoaching,type Analysis} from '@/lib/coaching-client';
export type {Analysis} from '@/lib/coaching-client';

// Rear-view figure in a trophy-like pose, keyed by COCO joint index so focus joints map directly.
const FIGURE:Record<number,[number,number]>={5:[40,42],6:[60,42],7:[30,31],9:[27,13],8:[70,54],10:[77,40],11:[44,84],12:[56,84],13:[41,113],14:[59,113],15:[39,146],16:[61,146]};
const FIGURE_BONES=[[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
export function BodyMap({joints,marks=joints,label,size='md'}:{joints:number[];marks?:number[];label:string;size?:'sm'|'md'}){
 const on=new Set(joints);
 return <svg className={`body-map body-map-${size}`} viewBox="0 0 100 156" role="img" aria-label={`Body diagram highlighting ${label}`}>
  <circle className={`body-head ${on.has(0)?'on':''}`} cx="50" cy="25" r="9"/>
  {FIGURE_BONES.map(([a,b])=><line key={`${a}-${b}`} className={on.has(a)&&on.has(b)?'on':''} x1={FIGURE[a][0]} y1={FIGURE[a][1]} x2={FIGURE[b][0]} y2={FIGURE[b][1]}/>)}
  {marks.filter(j=>FIGURE[j]).map(j=><g key={j}><circle className="body-halo" cx={FIGURE[j][0]} cy={FIGURE[j][1]} r="7"/><circle className="body-joint" cx={FIGURE[j][0]} cy={FIGURE[j][1]} r="3.2"/></g>)}
 </svg>;
}

function LookingAt({focus,tags,compact}:{focus:BodyFocus;tags:string[];compact?:boolean}){
 return <header className={`looking-at ${compact?'compact':''}`}>
  <BodyMap joints={focus.joints} marks={focus.marks} label={focus.part} size={compact?'sm':'md'}/>
  <div><span className="eyebrow">LOOKING AT</span><strong>{focus.part}</strong>{!compact&&<p>{focus.look}</p>}<div className="focus-tags">{tags.filter(Boolean).map(t=><span key={t}>{t}</span>)}</div></div>
 </header>;
}
const range=(s?:Stage)=>s&&s.start!==null&&s.end!==null?`${s.start.toFixed(2)}–${s.end.toFixed(2)}s`:'';

export function CoachFeedback({analysis:a,stages=[],handedness,selected,onSeek,onSelect}:{analysis:Analysis;stages?:Stage[];handedness?:string;selected?:string;onSeek?:(time:number)=>void;onSelect?:(id:string)=>void}){
 const status=a.model_status==='completed'?'YOUR PRACTICE PLAN':a.model_status==='insufficient_evidence'?'A CLEARER RECORDING':'REVIEWED PRACTICE CARD';
 const stage=stages.find(s=>s.id===a.stage_id),focus=bodyFocus(a.focus_id==='recapture'?'recapture':a.stage_id,handedness);
 const rows:[string,string][]=([['What we saw',a.observation],['Why it matters',a.rationale],['Try this',a.drill],['What to check',a.success_check]] as [string,string][]).filter(([,v])=>v);
 return <article className="coach-feedback">
  {/* The stage card above already shows the selected stage in full; here it shrinks to a tag until the user moves elsewhere. */}
  <div className="feedback-top"><span className="pill">{status}</span>{focus&&selected===a.stage_id&&<span className="focus-tag">{focus.part} · {stage?.label}</span>}</div>
  {focus&&selected!==a.stage_id&&<LookingAt compact focus={focus} tags={[stage?.label||'',range(stage)]}/>}
  <h3>{a.title}</h3>
  {a.cue&&<blockquote className="feedback-cue"><span className="eyebrow">YOUR CUE</span>{a.cue}</blockquote>}
  <dl className="feedback-rows">{rows.map(([k,v],i)=><div key={k}><dt><i>{i+1}</i>{k}</dt><dd>{v}</dd></div>)}</dl>
  {a.evidence_times.length>0&&<div className="coach-evidence"><span className="eyebrow">EVIDENCE FRAMES</span><div>{a.evidence_times.map(t=><button key={t} onClick={()=>{onSeek?.(t);if(a.stage_id)onSelect?.(a.stage_id);}} disabled={!onSeek}>▶ {t.toFixed(2)}s</button>)}</div></div>}
  <p className="feedback-limit">{a.limitation}<small>{a.source}</small></p>
  {!['completed','insufficient_evidence'].includes(a.model_status)&&<p role="status" className="feedback-status">{a.model_status==='busy'?'Gemma 4 is busy.':a.model_status==='reply_rejected'?'The model response did not pass the feedback checks.':'Gemma 4 is unavailable.'} Showing the reviewed fallback; you can try again.</p>}
 </article>;
}

/** The selected stage, read from the body part it is measured on. */
function StageFocus({stages,stage,handedness,onReplay,onSelect}:{stages:Stage[];stage:Stage;handedness?:string;onReplay:(s:Stage)=>void;onSelect:(id:string)=>void}){
 const focus=bodyFocus(stage.id,handedness),evidence=stage.evidence[0],index=stages.indexOf(stage);
 const metrics=Object.entries(evidence?.measurements||{}).map(([k,v])=>({key:k,...formatMeasurement(k,v)}));
 const go=(step:number)=>{const next=stages[index+step];if(!next)return;onSelect(next.id);if(next.status==='estimated')onReplay(next);};
 return <section className="stage-focus" aria-live="polite">
  <div className="stage-focus-nav"><span className="eyebrow">STAGE {index+1} OF {stages.length}</span><div><button aria-label="Previous stage" disabled={index<=0} onClick={()=>go(-1)}>←</button><button aria-label="Next stage" disabled={index>=stages.length-1} onClick={()=>go(1)}>→</button></div></div>
  {focus?<LookingAt focus={focus} tags={[stage.label,range(stage)]}/>:<h3>{stage.label}</h3>}
  <dl className="feedback-rows">
   <div><dt>Seen</dt><dd>{evidence?.observation||stage.detail}</dd></div>
   {metrics.length>0&&<div><dt>Measured</dt><dd className="stage-metrics">{metrics.map(m=><span key={m.key} title={m.hint}><small>{m.label}</small><b>{m.value}</b></span>)}</dd></div>}
  </dl>
  {stage.status==='estimated'?<button className="text-button stage-replay" onClick={()=>onReplay(stage)}>▶ Replay {stage.label.toLowerCase()} · 0.25×</button>:<p className="feedback-limit">This stage couldn’t be identified in this recording. That means not enough evidence, not a fault.</p>}
 </section>;
}

export function MovementInsight({jobId,stages,active,handedness,onReplay,onSelect,onSeek}:{jobId:string;stages:Stage[];active:string;handedness?:string;onReplay:(s:Stage)=>void;onSelect:(id:string)=>void;onSeek?:(time:number)=>void}){
 const requestVersion=useRef(0);
 const [analysis,setAnalysis]=useState<Analysis|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState('');
 const stage=stages.find(s=>s.id===active)||stages.find(s=>s.id==='loading')||stages[0];
 async function analyse(){
  const version=++requestVersion.current;setBusy(true);setError('');
  try{
   const d=await loadCoaching(jobId);
   if(version!==requestVersion.current)return;
   setAnalysis(d);if(d.stage_id&&stages.some(s=>s.id===d.stage_id))onSelect(d.stage_id);
  }catch(e){if(version===requestVersion.current)setError(e instanceof Error?e.message:'Coaching unavailable. Please try again.');}
  finally{if(version===requestVersion.current)setBusy(false);}
 }
 useEffect(()=>{setAnalysis(null);void analyse();return()=>{requestVersion.current++;};},[jobId]);
 return <div className="movement-insight">
  {stage&&<StageFocus stages={stages} stage={stage} handedness={handedness} onReplay={onReplay} onSelect={onSelect}/>}
  <div className="gemma-review"><span className="eyebrow">ONE FOCUS FOR YOUR NEXT REP</span>
   {!analysis&&<p>Your tracked movement selects a practice card. Gemma 4 on Ventuno phrases its approved cue; the drill and check stay unchanged.</p>}
   <div aria-live="polite">{error&&<p role="alert" className="error">{error}</p>}{analysis&&<CoachFeedback analysis={analysis} stages={stages} handedness={handedness} selected={stage?.id} onSeek={onSeek} onSelect={onSelect}/>}</div>
   <button className={analysis?'text-button gemma-again':'primary'} disabled={busy} onClick={analyse}>{busy?'Gemma 4 is preparing your practice plan…':analysis?'Review again with Gemma 4 ↻':<>Get coaching with Gemma 4 <span>↗</span></>}</button>
  </div>
 </div>;
}
