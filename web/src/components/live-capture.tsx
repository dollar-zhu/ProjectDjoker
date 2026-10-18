'use client';
import {useEffect,useRef,useState} from 'react';
import type {Options} from '@/lib/contracts';
import {LiveAudio} from './live-audio';

type Live={active:boolean;state:string;message:string;elapsed?:number;jobId?:string;updated?:number;mode?:'auto'|'manual';countdown?:number|null;readyProgress?:number};
export function CaptureCue({live}:{live:Omit<Live,'message'>}){
 if(!live.active||live.mode!=='auto')return null;
 if(live.state==='countdown')return <div className="capture-cue" role="status" aria-label={`Serve starts in ${live.countdown??'a moment'}`}><span>GET READY</span><strong>{live.countdown??'…'}</strong><p>Lower your hand. Serve on GO.</p></div>;
 if(live.state==='recording'&&(live.elapsed??0)<1)return <div className="capture-cue go" role="status"><strong>GO</strong><p>Perform your whole serve.</p></div>;
 if(live.state==='waiting'&&(live.readyProgress??0)>0)return <div className="ready-cue" role="status">Hold your hand here…<progress aria-label="Ready gesture hold" max="1" value={live.readyProgress}/></div>;
 return null;
}
export function LiveCapture({onReview}:{onReview:(id:string)=>void}){
 const [live,setLive]=useState<Live>({active:false,state:'stopped',message:'Camera is off.'});
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[frame,setFrame]=useState('');
 const [mode,setMode]=useState<'auto'|'manual'>('auto');
 const [audioStopped,setAudioStopped]=useState(false);
 const [view,setView]=useState<Options['view']>('rear');
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
    if(s.jobId&&s.state!=='processing'&&s.jobId!==delivered.current){delivered.current=s.jobId;callback.current(s.jobId);}
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
 return <section className="live-panel panel" aria-label="Ventuno live capture">
  <div className="panel-head"><div><span className="eyebrow">VENTUNO WEBCAM</span><h2>Serve. We’ll catch it.</h2></div><span className={`pill ${live.state==='recording'?'amber':''}`}>{live.state.toUpperCase()}{live.state==='recording'?` · ${live.elapsed?.toFixed(1)||'0.0'}s`:''}</span></div>
  <div className="live-content">
   <div className="live-preview">{frame&&live.active?<img src={frame} alt="Live Ventuno webcam with tracked body joints"/>:<div className="live-placeholder">↗<p>Step into frame.<br/>Raise a hand to get ready.</p></div>}<CaptureCue live={live}/>{live.state==='processing'&&<div className="live-processing">Preparing your review…</div>}</div>
   <div className="live-controls"><p className="observation" role="status">{live.message}</p>
    <p>{(live.active?live.mode:mode)==='manual'?'Press Start recording, perform one serve, then Stop & analyse. Tracking loss will not discard your video. The 19-second limit saves the clip automatically.':'Keep your whole body visible. Raise either hand to shoulder height and hold briefly. A 3-second countdown gives you time to lower your hand and prepare. Serve on GO, then stay in frame through the finish.'}</p>
    <label className="field">Capture mode<select value={live.active?live.mode||'auto':mode} disabled={live.active||busy} onChange={e=>setMode(e.target.value as 'auto'|'manual')}><option value="auto">Ready gesture · automatic capture</option><option value="manual">Manual recording · debug tracking</option></select></label>
    <label className="field">Camera view<select value={view} disabled={live.active||busy} onChange={e=>setView(e.target.value as Options['view'])}><option value="rear">Behind the server</option><option value="side">Side of the server</option></select></label>
    {live.active&&live.mode==='manual'&&<button className="primary" disabled={busy||!['ready','recording'].includes(live.state)} onClick={()=>control(live.state==='recording'?'finish':'record')}>{live.state==='recording'?'Stop & analyse':live.state==='processing'?'Analysing…':'Start recording'} <span>{live.state==='recording'?'■':'●'}</span></button>}
    <button className="primary" disabled={busy} onClick={()=>control(live.active?'stop':'start')}>{busy?'Please wait…':live.active?'Stop camera':'Start camera'} <span>{live.active?'■':'↗'}</span></button>
    {error&&<div className="error" role="alert">{error}</div>}
    <LiveAudio active={live.active&&!audioStopped}/>
    <p className="small muted">Right-handed serves only. Live tracking runs on this Mac; saved clips use the existing Ventuno analysis. Motion completion is an estimate, not detected ball contact. Capture pauses while preparing each review.</p>
   </div>
  </div>
 </section>;
}
