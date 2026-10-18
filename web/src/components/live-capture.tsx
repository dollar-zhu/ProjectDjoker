'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {reviewFromCapture,type CaptureSnapshot} from '@/lib/capture-navigation';
import type {Options} from '@/lib/contracts';
import {LiveAudio} from './live-audio';

type Mode='continuous'|'auto'|'manual';
type Capture={number:number;jobId:string|null;status:'saving'|'processing'|'complete'|'failed';at:number;warning?:string|null};
type Live={active:boolean;state:string;message:string;elapsed?:number;jobId?:string;updated?:number;mode?:Mode;countdown?:number|null;readyProgress?:number;captures?:Capture[];lastEvent?:{event:string;number:number;at:number}};
const MODE_LABEL:Record<Mode,string>={continuous:'Continuous',auto:'Ready gesture',manual:'Manual'};
const CAPTURE_LABEL:Record<Capture['status'],string>={saving:'Saving…',processing:'Preparing review…',complete:'Review ready',failed:'Review failed · open to retry'};
export function CaptureCue({live}:{live:Omit<Live,'message'>}){
 if(live.active&&live.mode==='continuous'){
  const last=live.lastEvent,recent=last&&last.event!=='start'&&(live.updated??0)-last.at<3&&live.state!=='recording';
  if(recent&&last.event==='complete')return <div className="capture-cue go" role="status"><strong>✓</strong><p>Serve {last.number} captured</p></div>;
  if(recent&&last.event==='discard')return <div className="ready-cue" role="status">Not a complete serve · still watching</div>;
  if(live.state==='waiting'&&(live.readyProgress??0)>0)return <div className="ready-cue" role="status">Getting set…<progress aria-label="Settled stance" max="1" value={live.readyProgress}/></div>;
  if(live.state==='watching')return <div className="ready-cue" role="status">Watching · serve when ready</div>;
  if(live.state==='recording')return <div className="ready-cue" role="status">Serve detected…</div>;
  return null;
 }
 if(!live.active||live.mode!=='auto')return null;
 if(live.state==='countdown')return <div className="capture-cue" role="status" aria-label={`Serve starts in ${live.countdown??'a moment'}`}><span>GET READY</span><strong>{live.countdown??'…'}</strong><p>Lower your hand. Serve on GO.</p></div>;
 if(live.state==='recording'&&(live.elapsed??0)<1)return <div className="capture-cue go" role="status"><strong>GO</strong><p>Perform your whole serve.</p></div>;
 if(live.state==='waiting'&&(live.readyProgress??0)>0)return <div className="ready-cue" role="status">Hold your hand here…<progress aria-label="Ready gesture hold" max="1" value={live.readyProgress}/></div>;
 return null;
}
export function LiveCapture({onReview}:{onReview:(id:string)=>void}){
 const [live,setLive]=useState<Live>({active:false,state:'stopped',message:'Camera is off.'});
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[frame,setFrame]=useState('');
 const [mode,setMode]=useState<Mode>('continuous');
 const [audioStopped,setAudioStopped]=useState(false);
 const [view,setView]=useState<Options['view']>('rear');
 const previous=useRef<CaptureSnapshot|null>(null);
 const delivered=useRef<string|undefined>(undefined),callback=useRef(onReview);
 useEffect(()=>{callback.current=onReview;},[onReview]);
 useEffect(()=>{
  let ended=false,timer:ReturnType<typeof setTimeout>;
  async function poll(){
   try{
    const r=await fetch('/api/live',{cache:'no-store'});if(!r.ok)throw Error('Could not read camera status.');
    const s:Live=await r.json();if(ended)return;
    setLive(s);
    if(s.active&&s.state!=='starting')setFrame('/api/live/frame?stream=1');
    // Continuous capture keeps the player on this page; serves are listed below.
    const reviewId=s.mode==='continuous'?null:reviewFromCapture(previous.current,s);previous.current=s;
    if(reviewId&&reviewId!==delivered.current){delivered.current=reviewId;callback.current(reviewId);}
   }catch(e){if(!ended)setError((e as Error).message);}
   if(!ended)timer=setTimeout(poll,300);
  }
  poll();return()=>{ended=true;clearTimeout(timer);};
 },[]);
 async function control(action:'start'|'stop'|'record'|'finish'){
  if(action==='stop')setAudioStopped(true);
  if(action==='start')setAudioStopped(false);
  setBusy(true);setError('');
  try{
   const r=await fetch('/api/live',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,mode,options:{crop:[0,0,1,1],view,handedness:'right'}})});
   const s=await r.json();if(!r.ok)throw Error(s.error||'Live capture is already running.');setLive(s);
  }catch(e){setError((e as Error).message);if(action==='stop')setAudioStopped(false);}finally{setBusy(false);}
 }
 const current=(live.active?live.mode:mode)||'auto',manual=current==='manual';
 const captures=(live.captures||[]).filter(c=>c.jobId);
 return <section className="coach-recorder" aria-label="Ventuno live capture">
  <div className="coach-camera">
   <div className="coach-camera-bar"><span><i className={live.state==='recording'?'recording-dot':''}/>LIVE CAMERA</span><span>{live.state==='recording'?`Recording · ${live.elapsed?.toFixed(1)||'0.0'}s`:live.active?(current==='continuous'&&captures.length?`${captures.length} serve${captures.length>1?'s':''} captured`:'Ventuno webcam'):'Camera off'}</span></div>
   <div className="live-preview">{frame&&live.active?<img src={frame} alt="Live Ventuno webcam with tracked body joints"/>:<div className="coach-camera-off"><svg viewBox="0 0 240 180" aria-hidden="true"><path d="M50 160L85 25H155L190 160ZM68 90H172M78 55H162M120 55V140M56 140H184M95 25L78 160M145 25L162 160"/><circle cx="145" cy="65" r="6"/></svg><p>Your court. Your camera.</p><small>Start the camera to see your live preview.</small></div>}<CaptureCue live={live}/>{live.state==='processing'&&<div className="live-processing" role="status">Serve saved. Preparing your review…</div>}</div>
   <div className="coach-camera-bar coach-camera-bottom"><span>Keep your full body in frame</span><span>{view==='rear'?'Rear':'Side'} view · {MODE_LABEL[current]} capture</span></div>
  </div>
  <div className="coach-capture-controls">
   <span className="eyebrow">READY WHEN YOU ARE</span><h1>Just you.<br/><em>And your serve.</em></h1>
   <p className="coach-intro">{manual?'Record one serve. Finish the motion, then open your review.':current==='continuous'?'Step into frame and serve. Every serve is captured and reviewed while you keep going.':'Step into frame. Raise a hand. We’ll catch the serve and take you straight to your review.'}</p>
   <p className="coach-live-status" role="status">{live.message}</p>
   {captures.length>0&&<div className="coach-recent-list" aria-label="Serves captured this session">{captures.map(c=><Link key={c.number} href={`/serves/${c.jobId}`}><span>Serve {c.number}<small>{CAPTURE_LABEL[c.status]}{c.warning&&<> · <strong>{c.warning}</strong></>}</small></span><span>↗</span></Link>)}</div>}
   {live.active&&manual&&<button className="primary" disabled={busy||!['ready','recording'].includes(live.state)} onClick={()=>control(live.state==='recording'?'finish':'record')}>{live.state==='recording'?'Stop & analyse':live.state==='processing'?'Analysing…':'Start recording'} <span>{live.state==='recording'?'■':'●'}</span></button>}
   <button className={live.active?'coach-stop-camera':'primary coach-start-camera'} disabled={busy} onClick={()=>control(live.active?'stop':'start')}>{busy?'Please wait…':live.active?'Stop camera':'Start camera'} <span>{live.active?'■':'↗'}</span></button>
   {error&&<div className="error" role="alert">{error}</div>}
   <LiveAudio active={live.active&&!audioStopped}/>
   <details className="coach-settings"><summary>Camera settings & positioning</summary>
    <label className="field">Capture mode<select value={live.active?live.mode||'auto':mode} disabled={live.active||busy} onChange={e=>setMode(e.target.value as Mode)}><option value="continuous">Continuous · every serve</option><option value="auto">Ready gesture · automatic capture</option><option value="manual">Manual recording</option></select></label>
    <label className="field">Camera view<select value={view} disabled={live.active||busy} onChange={e=>setView(e.target.value as Options['view'])}><option value="rear">Behind the server</option><option value="side">Side of the server</option></select></label>
    <p>{manual?'Press Start recording, perform one serve, then Stop & analyse. The 19-second limit saves your clip automatically.':current==='continuous'?'Stand still in frame for a moment, then serve. Each reach and follow-through is saved with the setup before it; settle again between serves. Any overhead arm movement that finishes like a serve can be captured.':'Raise either hand to shoulder height and hold briefly. A 3-second countdown gives you time to lower your hand. Serve on GO and stay in frame through the finish.'}</p>
    <p className="small muted">Right-handed serves, rear or side view. Motion completion is estimated from body movement.</p>
   </details>

  </div>
 </section>;
}
