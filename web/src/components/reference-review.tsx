'use client';
import {useEffect,useMemo,useState,useRef} from 'react';
import {phaseAt} from '@/lib/reference';
import {fitReference,alignedReference,loadingEvidence,type ReferenceOverlay} from '@/lib/overlay';
import {frameAt} from '@/lib/playback';
type PoseFrame={time:number;xy:number[][];scores:number[]};
type Reference={player:string;total:number;sourceTotal:number;excluded:number;selected:string;poses:number[][][];serves:{id:string;opponent:string;serveNumber:number;flags:string[]}[];source:string;license:string};
export function ReferenceReview({view,time,duration,events,frames,overlayActive,onOverlayChange}:{view:string;overlayActive:boolean;onOverlayChange:(value:ReferenceOverlay|null,play?:boolean)=>void;time:number;duration:number;events:{id:string;time:number}[];frames:PoseFrame[]}){
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
 const synced=phaseAt(time,duration,events);
 const load=events.find(e=>e.id==='loading')?.time;
 const loadFrame=load===undefined?null:frameAt(frames,load);
 const fit=useMemo(()=>view==='rear'&&data&&loadFrame?fitReference(data.poses[40],loadFrame):null,[view,data,loadFrame]);
 useEffect(()=>{commentVersion.current++;setComment(null);setCommentError('');return()=>{commentVersion.current++;};},[data,fit]);
 useEffect(()=>{if(overlayActive&&data&&fit)onOverlayChange({poses:data.poses,fit,player:data.player});},[data,fit,overlayActive,onOverlayChange]);
 const evidence=useMemo(()=>{
  if(!data||!fit||!loadFrame||load===undefined)return null;
  const ghost=alignedReference(data.poses[40],loadFrame,fit);
  return ghost?loadingEvidence(loadFrame,ghost,data.player,load):null;
 },[data,fit,loadFrame,load]);
 useEffect(()=>{setCommentBusy(false);},[evidence]);
 async function studyOverlay(){
  if(!data||!fit||synced===null)return;
  onOverlayChange({poses:data.poses,fit,player:data.player},true);
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
   <div className="overlay-actions"><button className="primary" disabled={synced===null||!fit} onClick={studyOverlay}>{overlayActive?'Replay overlay':'Overlay '+data.player.split(' ').at(-1)} · 0.25× <span>↗</span></button>{overlayActive&&<button className="text-button" onClick={()=>onOverlayChange(null)}>Hide overlay</button>}<p>Green is you. Blue dashed is the pro. Replay both movements together at quarter speed.</p>{(synced===null||!fit)&&<p>{view!=='rear'?'This reference set is for recordings from behind the server.':'Reliable loading/reach moments and torso tracking are needed to align the overlay.'}</p>}</div>
   <div className="comparison-commentary" aria-live="polite"><span className="eyebrow">YOUR PRACTICE FOCUS · LOADING{load!==undefined?` AT ${load.toFixed(2)}s`:''}</span>{comment?<><h3>{comment.observation}</h3><p className="practice-cue">{comment.cue}</p><small>{comment.source}{comment.model_status==='reply_rejected'?' · model reply did not pass the evidence check':''}</small><p>{comment.note}</p></>:<p>{commentBusy?'Gemma is reviewing the measured differences on Ventuno…':commentError||(!evidence?'Knee tracking is too uncertain for a practice suggestion.':`Click the overlay to study your loading position against ${data.player} and get a practice focus.`)}</p>}</div>
   <details className="reference-evidence"><summary>Reference source & limitations</summary><p>Individual serve: {data.selected}. Estimated 3D body poses; original broadcast video is not included. Joint mapping and phase labels remain provisional.</p><p>{data.total} of {data.sourceTotal} serves retained; {data.excluded} excluded for uncertain orientation. These are rear projections derived from body poses. The original recording’s camera view is unknown.</p><p>Source quality flags: {row?.flags.join(', ')||'None recorded'}. Default selection prioritizes stable event estimates; it is not a recommended ideal serve.</p><p>{data.source} · {data.license}. <a href="https://github.com/jasnwag/tennis_serve_dataset" target="_blank" rel="noreferrer">Dataset source ↗</a></p></details>
  </>}
 </section>;
}
