'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {designHref,type Concept} from '@/lib/design-flow';
import {compareMotion,referencePhaseAt,referencePoseAt} from '@/lib/motion-similarity';
import {alignedReference,REFERENCE_BONES,type PoseFrame} from '@/lib/overlay';
import {frameAt,type Stage} from '@/lib/playback';
import s from './prototype.module.css';

const SAVED_SERVE='f90f3a1c-8350-4577-9be8-64bcd3da994d';
const BONES=[[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
const concepts=[{id:'courtside',name:'Courtside',number:'01'},{id:'coach',name:'Coach',number:'02'},{id:'studio',name:'Studio',number:'03'}] as const;
type Job={id:string;meta:{width:number;height:number;duration:number};options:{view:string;handedness:string};result:{frames:PoseFrame[];events:{id:string;time:number}[];stages:Stage[]}};
type Reference={player:string;poses:number[][][]};
const timestamp=(t:number)=>`0:${t.toFixed(1).padStart(4,'0')}`;

export function DesignPrototype({concept,review}:{concept:Concept;review:boolean}){
 const router=useRouter();
 const [job,setJob]=useState<Job|null>(null),[reference,setReference]=useState<Reference|null>(null),[error,setError]=useState('');
 const [player,setPlayer]=useState('djokovic'),[overlay,setOverlay]=useState(true),[playing,setPlaying]=useState(false),[time,setTime]=useState(0),[speed,setSpeed]=useState('.25');
 const [active,setActive]=useState('loading'),[recording,setRecording]=useState(false),[countdown,setCountdown]=useState<number|null>(null),[settings,setSettings]=useState(false),[history,setHistory]=useState(false);
 const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null),end=useRef<number|null>(null);
 useEffect(()=>{
  const controller=new AbortController();
  fetch(`/api/jobs/${SAVED_SERVE}`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('The saved demo serve is unavailable. Open the original app to record a serve.');return r.json();}).then(setJob).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>controller.abort();
 },[]);
 useEffect(()=>{
  const controller=new AbortController();setReference(null);
  fetch(`/api/references?player=${player}&type=1`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('The player reference could not be loaded.');return r.json();}).then(setReference).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>controller.abort();
 },[player]);
 const comparison=useMemo(()=>job&&reference?compareMotion({...job.result,reference:reference.poses,duration:job.meta.duration,...job.options}):null,[job,reference]);
 const stage=job?.result.stages.find(x=>x.id===active),evidence=stage?.evidence[0];
 useEffect(()=>{
  if(!review||!job||!video.current)return;
  const t=job.result.events.find(x=>x.id==='loading')?.time||0;
  video.current.currentTime=t;video.current.playbackRate=.25;setTime(t);
 },[job,review]);
 useEffect(()=>{
  if(countdown===null)return;
  const timer=setTimeout(()=>{
   if(countdown>1)setCountdown(countdown-1);
   else{setCountdown(null);setRecording(true);if(video.current){video.current.currentTime=0;video.current.playbackRate=1;video.current.play().catch(()=>{});}}
  },1000);
  return()=>clearTimeout(timer);
 },[countdown]);
 useEffect(()=>{
  if(!recording)return;
  const timer=setTimeout(()=>router.push(designHref(concept,true)),4200);
  return()=>clearTimeout(timer);
 },[recording,concept,router]);
 useEffect(()=>{
  let frame=0;
  function draw(){
   const c=canvas.current,v=video.current,ctx=c?.getContext('2d');
   if(c&&v&&ctx&&job){
    if(end.current!==null&&v.currentTime>=end.current){v.pause();end.current=null;}
    ctx.clearRect(0,0,c.width,c.height);
    if(review){
     const pose=frameAt(job.result.frames,v.currentTime);
     if(pose){
      ctx.lineCap='round';ctx.lineJoin='round';ctx.lineWidth=3;ctx.strokeStyle='#d4fb79';ctx.fillStyle='#d4fb79';
      for(const [a,b] of BONES){if(pose.scores[a]<.3||pose.scores[b]<.3)continue;ctx.beginPath();ctx.moveTo(pose.xy[a][0],pose.xy[a][1]);ctx.lineTo(pose.xy[b][0],pose.xy[b][1]);ctx.stroke();}
      pose.xy.forEach(([x,y],i)=>{if(pose.scores[i]>=.3){ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();}});
      if(overlay&&reference&&comparison?.alignment&&comparison.fit){
       const phase=referencePhaseAt(comparison.alignment,v.currentTime),ref=phase===null?null:referencePoseAt(reference.poses,phase),ghost=ref?alignedReference(ref,pose,comparison.fit):null;
       if(ghost){ctx.save();ctx.strokeStyle='#77c9ff';ctx.fillStyle='#77c9ff';ctx.lineWidth=3;ctx.setLineDash([6,4]);for(const [a,b]of REFERENCE_BONES){ctx.beginPath();ctx.moveTo(ghost[a][0],ghost[a][1]);ctx.lineTo(ghost[b][0],ghost[b][1]);ctx.stroke();}ctx.restore();}
      }
     }
    }
   }
   frame=requestAnimationFrame(draw);
  }
  draw();return()=>cancelAnimationFrame(frame);
 },[job,review,overlay,reference,comparison]);
 function seek(t:number){if(video.current){end.current=null;video.current.pause();video.current.currentTime=t;setTime(t);}}
 function replay(){if(!video.current||!stage||stage.start===null||stage.end===null)return;const v=video.current;v.currentTime=stage.start;end.current=stage.end;v.playbackRate=.25;setSpeed('.25');v.play().catch(()=>setError('Press play to replay the video.'));}
 const recordButton=<button className={s.recordButton} disabled={!job||countdown!==null} onClick={()=>recording?router.push(designHref(concept,true)):setCountdown(3)}><span className={recording?s.stopIcon:s.recordIcon}/>{recording?'Finish & review':countdown!==null?'Get ready…':'Try recording flow'}<span className={s.arrow}>↗</span></button>;
 const captureHelp=<div className={s.captureHelp}><span className={s.kicker}>READY WHEN YOU ARE</span><h1>Just you.<br/><em>And your serve.</em></h1><p>Step into frame. Raise a hand.<br/>We’ll catch the serve and take you<br className={s.desktopBreak}/> straight to your review.</p><div className={s.instructions}><span><b>01</b> Keep your whole body in frame</span><span><b>02</b> Raise a hand to start the countdown</span><span><b>03</b> Serve, finish, and see your feedback</span></div>{recordButton}<small>Interactive demo · uses a saved recording</small><Link href={designHref(concept,true)} className={s.skip}>Or go straight to the review ↗</Link></div>;
 const score=<div className={s.scoreBlock}><div><span className={s.kicker}>MOVEMENT SIMILARITY</span><div className={s.score}>{comparison?.status==='available'?comparison.score:'—'}<span>/100</span></div></div><div className={s.scoreCaption}><b>vs. {reference?.player||'reference player'}</b><p>{comparison?.status==='available'?`${Math.round(comparison.coverage*100)}% joint coverage · ${comparison.quality==='partial'?'partial tracking':'full tracking'}`:'Waiting for enough tracked movement'}</p></div><small>Experimental comparison, not a technique grade.</small></div>;
 const feedback=<div className={s.feedback}><div className={s.feedbackHeading}><span className={s.kicker}>YOUR NEXT FOCUS</span><span>↗</span></div><h2>{stage?.label||'Loading'}</h2><p>{evidence?.observation||stage?.detail||'Loading the measured feedback…'}</p><div className={s.cue}><span>TRY THIS ON REPLAY</span><p>{evidence?.cue||'Keep your full body in frame through the end of your serve.'}</p></div><button className={s.replay} onClick={replay} disabled={stage?.status!=='estimated'}>▶ Replay this moment <span>0.25×</span></button></div>;
 const referencePicker=<div className={s.referencePicker}><label>Compare with<select aria-label="Compare with player" value={player} onChange={e=>setPlayer(e.target.value)}><option value="djokovic">Novak Djokovic</option><option value="sinner">Jannik Sinner</option></select></label><button className={`${s.toggle} ${overlay?s.on:''}`} aria-label="Professional player overlay" aria-pressed={overlay} onClick={()=>setOverlay(!overlay)}><i/>Overlay</button></div>;
 const sequence=<div className={s.sequence} aria-label="Serve phases">{job?.result.stages.map((item,i)=><button key={item.id} className={active===item.id?s.activePhase:''} disabled={item.time===null} onClick={()=>{setActive(item.id);if(item.time!==null)seek(item.time);}}><small>0{i+1}</small><b>{['Setup','Toss','Loading','Reach','Follow-through','Finish'][i]}</b><span>{item.time===null?'Not tracked':`${item.time.toFixed(2)}s`}</span></button>)}</div>;
 const media=<div className={s.media}>
  <div className={s.mediaTop}><span className={s.mediaLabel}><i className={recording?s.redDot:''}/>{review?'SAVED SERVE · 01':recording?'RECORDING DEMO':'CAMERA PREVIEW · DEMO'}</span><div className={s.mediaTopActions}>{review?<Link href={designHref(concept,false)}>＋ New serve</Link>:<><button onClick={()=>setHistory(!history)} aria-expanded={history}>↶ Recent serves</button><button aria-label="Camera settings" onClick={()=>setSettings(!settings)} aria-expanded={settings}>⚙</button></>}</div></div>
  <div className={s.frame}>
   {job?<><video ref={video} src={`/api/jobs/${job.id}/video.mp4`} poster={`/api/jobs/${job.id}/poster.jpg`} playsInline muted preload="auto" onTimeUpdate={e=>setTime(e.currentTarget.currentTime)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>{setPlaying(false);if(recording)router.push(designHref(concept,true));}}/><canvas ref={canvas} width={job.meta.width} height={job.meta.height} aria-label={review?'Your tracked movement with a professional player pose overlay':'Saved recording preview'}/></>:<div className={s.loading}>Loading saved recording…</div>}
   {!review&&<div className={s.framingGuide}><i/><i/><i/><i/></div>}
   {countdown!==null&&<div className={s.countdown} role="status"><small>GET READY</small><strong>{countdown}</strong><span>Lower your hand. Serve on GO.</span></div>}
  </div>
  {review?<><div className={s.legend}><span><i/>You</span><span><i/>{reference?.player||'Pro reference'}</span><span>Aligned to your movement</span></div><div className={s.transport}><button aria-label={playing?'Pause serve':'Play serve'} onClick={()=>{if(!video.current)return;end.current=null;video.current.paused?video.current.play().catch(()=>{}):video.current.pause();}}>{playing?'Ⅱ':'▶'}</button><span>{timestamp(time)}</span><input aria-label="Scrub serve" type="range" min="0" max={job?.meta.duration||1} step=".01" value={time} onChange={e=>seek(+e.target.value)}/><span>{timestamp(job?.meta.duration||0)}</span><select aria-label="Video playback speed" value={speed} onChange={e=>{setSpeed(e.target.value);if(video.current)video.current.playbackRate=+e.target.value;}}><option value=".25">0.25×</option><option value=".5">0.5×</option><option value="1">1×</option></select></div></>:<div className={s.cameraBottom}><span><i/>{recording?'Capturing the full movement…':'Full body in frame'}</span><span>Rear view · Auto capture</span></div>}
  {settings&&<div className={s.popover}><b>Camera setup</b><p>Rear view · right-handed serve</p><p>Raise a hand, wait for the countdown, then serve. This demo uses saved footage.</p><button onClick={()=>setSettings(false)}>Got it</button></div>}
  {history&&<div className={s.popover}><b>Recent serves</b><Link href={designHref(concept,true)}>Saved serve · review ready ↗</Link><a href="/">Open all recordings ↗</a></div>}
 </div>;
 return <div className={`${s.prototype} ${s[concept]} ${review?s.review:s.capture}`}>
  <div className={s.workspace}>
   {error&&<div role="alert" className={s.error}>{error}</div>}
   {!review?<div className={s.captureLayout}>{media}{captureHelp}</div>:<div className={s.reviewLayout}>
    <div className={s.videoColumn}>{media}{concept!=='courtside'&&sequence}{concept==='studio'&&<div className={s.studioFeedback}>{feedback}</div>}</div>
    <aside className={s.reviewAside}><div className={s.reviewTitle}><div><span className={s.kicker}>ONE SERVE. ONE STEP FORWARD.</span><h1>Your serve,<br/><em>in focus.</em></h1></div><span className={s.ball}>↗</span></div>{score}{referencePicker}{concept!=='studio'&&feedback}<Link className={s.nextServe} href={designHref(concept,false)}>Record another serve <span>↗</span></Link></aside>
    {concept==='courtside'&&sequence}
   </div>}
  </div>
  <nav className={s.designDock} aria-label="Design prototypes"><div className={s.dockLabel}>DESIGN<br/>EXPLORATIONS</div>{concepts.map(c=><Link key={c.id} href={designHref(c.id,review)} className={concept===c.id?s.selectedDesign:''} aria-current={concept===c.id?'page':undefined}><small>{c.number}</small>{c.name}</Link>)}<div className={s.dockDivider}/><Link className={s.stageLink} href={designHref(concept,!review)}>{review?'← Recorder':'See review ↗'}</Link><span className={s.demoTag}>PROTOTYPE</span></nav>
 </div>;
}
