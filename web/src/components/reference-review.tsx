'use client';
import {useEffect,useMemo,useState,useRef} from 'react';
import {compareMotion} from '@/lib/motion-similarity';
import {alignedReference,loadingEvidence,type ReferenceOverlay} from '@/lib/overlay';
import {frameAt,type Stage} from '@/lib/playback';
type PoseFrame={time:number;xy:number[][];scores:number[]};
type Reference={player:string;total:number;sourceTotal:number;excluded:number;selected:string;poses:number[][][];serves:{id:string;opponent:string;serveNumber:number;flags:string[]}[];source:string;license:string};
type ScoreSummary={status:string;score?:number;coverage?:number;reason?:string;quality?:'full'|'partial';excludedMeasurements?:string[];regionCoverage?:{hittingArm:number;tossingArm:number;legs:number;torso:number}};
export function SimilaritySummary({player,comparison}:{player:string;comparison:ScoreSummary}){
 return <div className="motion-score" aria-live="polite">
  <span className="eyebrow">EXPERIMENTAL BODY SIMILARITY</span>
  {comparison.status==='available'?<><div className="score-value"><strong>{comparison.score}</strong><span>/ 100</span></div><p>Compared with the selected {player} serve. More similar tracked body positions give a higher score.</p>
   {comparison.coverage!==undefined&&<div className="tracking-coverage"><span className="pill">{Math.round(comparison.coverage*100)}% joint coverage</span>{comparison.quality==='partial'&&<p>Some joints were obscured. The score uses the visible movement; hidden positions are excluded.</p>}</div>}
   {comparison.regionCoverage&&<details className="score-evidence"><summary>What was compared</summary><dl>{([['hittingArm','Hitting arm'],['tossingArm','Tossing arm'],['legs','Legs'],['torso','Torso']] as const).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{Math.round(comparison.regionCoverage![key]*100)}% tracked</dd></div>)}</dl>{comparison.excludedMeasurements?.map(note=><p key={note}>{note}</p>)}</details>}
   <p>Movement phases are aligned to allow different speeds. This is similarity, not technique quality or a calibrated percentage.</p></>:<><h3>Score unavailable</h3><p>{comparison.reason}</p><p>There is not enough visible movement to make a useful comparison.</p></>}
 </div>;
}
export function ReferenceReview({view,handedness,duration,events,frames,stages,overlayActive,onOverlayChange}:{view:string;handedness:string;overlayActive:boolean;onOverlayChange:(value:ReferenceOverlay|null,play?:boolean)=>void;duration:number;events:{id:string;time:number}[];frames:PoseFrame[];stages?:Stage[]}){
 const commentVersion=useRef(0);
 const [player,setPlayer]=useState('djokovic'),[type,setType]=useState('1'),[serve,setServe]=useState('');
 const [comment,setComment]=useState<{observation:string;cue:string;source:string;model_status:string;note:string}|null>(null),[commentBusy,setCommentBusy]=useState(false),[commentError,setCommentError]=useState('');
 const [data,setData]=useState<Reference|null>(null),[error,setError]=useState('');
 useEffect(()=>{
  const controller=new AbortController();setData(null);setError('');onOverlayChange(null);
  fetch(`/api/references?player=${player}&type=${type}${serve?'&serve='+encodeURIComponent(serve):''}`,{signal:controller.signal})
   .then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error);return d;}).then(setData)
   .catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>controller.abort();
 },[player,type,serve]);
 const comparison=useMemo(()=>data?compareMotion({frames,reference:data.poses,events,duration,view,handedness,stages}):null,[data,frames,events,duration,view,handedness,stages]);
 const load=events.find(e=>e.id==='loading')?.time;
 const loadFrame=load===undefined?null:frameAt(frames,load);
 const fit=comparison?.fit;
 const aligned=useMemo<ReferenceOverlay|null>(()=>data&&comparison?.alignment?.length&&fit?{poses:data.poses,fit,player:data.player,alignment:comparison.alignment,partial:comparison.status!=='available'}:null,[data,comparison,fit]);
 useEffect(()=>{commentVersion.current++;setComment(null);setCommentError('');return()=>{commentVersion.current++;};},[data,fit]);
 const evidence=useMemo(()=>{
  if(!data||!fit||!loadFrame||load===undefined)return null;
  const ghost=alignedReference(data.poses[40],loadFrame,fit);
  return ghost?loadingEvidence(loadFrame,ghost,data.player,load):null;
 },[data,fit,loadFrame,load]);
 useEffect(()=>{setCommentBusy(false);},[evidence]);
 async function studyOverlay(){
  if(!aligned)return;
  onOverlayChange(aligned,true);
  if(!evidence)return;
  const version=++commentVersion.current;setCommentBusy(true);setCommentError('');
  try{const r=await fetch('/api/commentary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(evidence)});const d=await r.json();if(!r.ok)throw Error(d.error);if(version===commentVersion.current)setComment(d);}
  catch(e){if(version===commentVersion.current)setCommentError((e as Error).message);}finally{if(version===commentVersion.current)setCommentBusy(false);}
 }
 const row=data?.serves.find(s=>s.id===data.selected);
 return <section className="reference-panel panel" aria-label="Professional serve reference">
  <div className="panel-head"><div><span className="eyebrow">COMPARE THE MOVEMENT</span><h2>Compare your serve</h2></div><span className="pill">EXPERIMENTAL</span></div>
  <div className="reference-controls">
   <label>Reference player<select aria-label="Reference player" value={player} onChange={e=>{setPlayer(e.target.value);setServe('');}}><option value="djokovic">Novak Djokovic</option><option value="sinner">Jannik Sinner</option></select></label>
   <label>Reference serve type<select aria-label="Reference serve type" value={type} onChange={e=>{setType(e.target.value);setServe('');}}><option value="1">First serve</option><option value="2">Second serve</option></select></label>
  </div>
  {error?<p className="error" role="alert">{error}</p>:!data?<p className="reference-loading" role="status">Loading reference movement…</p>:<>
   <div className="reference-selection"><label>Individual reference serve<select aria-label="Individual reference serve" value={data.selected} onChange={e=>setServe(e.target.value)}>{data.serves.map((s,i)=><option key={s.id} value={s.id}>{i+1}. vs {s.opponent}</option>)}</select></label><p>{data.serves.length} {type==='1'?'first':'second'} serves · fixed rear view</p></div>
   {comparison&&<SimilaritySummary player={data.player} comparison={comparison}/>}
   <div className="overlay-actions"><button className="primary" disabled={!aligned} onClick={studyOverlay}>{overlayActive?'Replay overlay':'Overlay '+data.player.split(' ').at(-1)} · 0.25× <span>↗</span></button>{overlayActive&&<button className="text-button" onClick={()=>onOverlayChange(null)}>Hide overlay</button>}<p>Green is you. Blue dashed is the pro. Their movement follows your pace within each serve phase.</p>{aligned&&<p>{aligned.partial?'Partial aligned replay':'Aligned serve'} · {aligned.alignment[0].time.toFixed(2)}–{aligned.alignment.at(-1)!.time.toFixed(2)}s. {aligned.partial?'Uncertain portions are excluded; a whole-motion score is unavailable.':'The score and replay use the same alignment.'}</p>}{!aligned&&<p>{comparison?.status==='unavailable'?comparison.reason:'Reliable movement and torso tracking are needed to align the overlay.'}</p>}</div>
   <div className="comparison-commentary" aria-live="polite"><span className="eyebrow">YOUR PRACTICE FOCUS · LOADING{load!==undefined?` AT ${load.toFixed(2)}s`:''}</span>{comment?<><h3>{comment.observation}</h3><p className="practice-cue">{comment.cue}</p><small>{comment.source}{comment.model_status==='reply_rejected'?' · model reply did not pass the evidence check':''}</small><p>{comment.note}</p></>:<p>{commentBusy?'Preparing the measured comparison…':commentError||(!evidence?'Knee tracking is too uncertain for a practice suggestion.':`Click the overlay to study your loading position against ${data.player} and get a practice focus.`)}</p>}</div>
   <details className="reference-evidence"><summary>Reference source & limitations</summary><p>Individual serve: {data.selected}. Estimated 3D body poses; original broadcast video is not included. Joint mapping and phase labels remain provisional.</p><p>{data.total} of {data.sourceTotal} serves retained; {data.excluded} excluded for uncertain orientation. These are rear projections derived from body poses. The original recording’s camera view is unknown.</p><p>Source quality flags: {row?.flags.join(', ')||'None recorded'}. Default selection prioritizes stable event estimates; it is not a recommended ideal serve.</p><p>{data.source} · {data.license}. <a href="https://github.com/jasnwag/tennis_serve_dataset" target="_blank" rel="noreferrer">Dataset source ↗</a></p></details>
  </>}
 </section>;
}
