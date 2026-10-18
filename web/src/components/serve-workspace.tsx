'use client';
import {useEffect,useRef,useState,useCallback,PointerEvent,type CSSProperties} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {CoachComparison} from '@/components/coach-comparison';
import {LiveCapture} from '@/components/live-capture';
import {alignedReference,REFERENCE_BONES,type ReferenceOverlay} from '@/lib/overlay';
import {referencePhaseAt,referencePoseAt} from '@/lib/motion-similarity';
import {frameAt,stagePlayback,type Stage} from '@/lib/playback';
import {MovementInsight} from '@/components/movement-review';
import {ServeTimeline} from '@/components/serve-timeline';
import {bodyFocus} from '@/lib/review-focus';
import type {Options} from '@/lib/contracts';

type Moment={id:string;label:string;time:number;detail:string};
type Result={stages?:Stage[];events:Moment[];frames:{time:number;xy:number[][];scores:number[]}[];feedback:{mode:string;observation:string;suggestion:string|null;drill:string|null};stats:{frames:number;sample_fps:number;mean_inference_ms:number|null;processing_seconds:number;backend:string};limitations:string[]};
type Job={id:string;name:string;status:string;stage:string;created:number;progress?:number;error?:string;view:Options['view'];suggestedCrop?:number[];meta?:{width:number;height:number;duration:number};options?:Options;result?:Result};
type Sample={id:string;name:string;label:string};
const BONES=[[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
const clock=(n:number)=>`${Math.floor(n/60)}:${(n%60).toFixed(2).padStart(5,'0')}`;
async function api(url:string,init?:RequestInit){const r=await fetch(url,init);const data=await r.json();if(!r.ok)throw Error(data.error||'The request failed.');return data;}

export function ServeWorkspace({jobId}:{jobId?:string}){
 const router=useRouter();
 const openServe=(id:string)=>router.push(`/serves/${id}`);
 const [job,setJob]=useState<Job|null>(null),[recent,setRecent]=useState<Job[]>([]),[health,setHealth]=useState<{connected:boolean;cpu:boolean;python:boolean;samples:Sample[]}|null>(null);
 const [uploading,setUploading]=useState(false),[error,setError]=useState(''),[crop,setCrop]=useState([.25,.05,.75,.98]);
 const [view,setView]=useState<Options['view']>('rear'),[hand,setHand]=useState<Options['handedness']>('right');
 const [editing,setEditing]=useState(true),[overlay,setOverlay]=useState(true),[time,setTime]=useState(0),[playing,setPlaying]=useState(false),[active,setActive]=useState('');
 const [referenceOverlay,setReferenceOverlay]=useState<ReferenceOverlay|null>(null),[rate,setRate]=useState('1'),[proVisible,setProVisible]=useState(true),[focusVisible,setFocusVisible]=useState(true);
 const focusRef=useRef<{joints:number[];label:string;start:number;end:number}|null>(null);
 const stageEnd=useRef<number|null>(null);
 const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null),input=useRef<HTMLInputElement>(null),start=useRef<number[]|null>(null);
 const working=!!job&&['queued','processing','preparing'].includes(job.status),result=job?.result;
 const refresh=()=>api('/api/clips').then(setRecent).catch(()=>{});
 useEffect(()=>{const check=()=>api('/api/health').then(setHealth).catch(()=>{});check();refresh();const timer=setInterval(check,10000);return()=>clearInterval(timer);},[]);
 useEffect(()=>{
  if(!jobId)return;
  const controller=new AbortController();
  fetch(`/api/jobs/${jobId}`,{signal:controller.signal}).then(async r=>{const j=await r.json();if(!r.ok)throw Error(j.error||'Serve not found.');return j;}).then(select).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>controller.abort();
 },[jobId]);
 const id=job?.id;
 useEffect(()=>{
  if(!id||!working)return;
  let stopped=false;
  const timer=setInterval(()=>api(`/api/jobs/${id}`).then(j=>{if(!stopped){setJob(j);if(j.status==='failed')setEditing(true);if(['complete','failed'].includes(j.status))refresh();}}).catch(e=>{if(!stopped)setError(e.message);}),1000);
  return()=>{stopped=true;clearInterval(timer);};
 },[id,working]);
 useEffect(()=>{
  let frame=0;
  function draw(){
   const c=canvas.current,v=video.current,ctx=c?.getContext('2d');
   if(c&&v&&ctx){
    if(stageEnd.current!==null&&v.currentTime>=stageEnd.current){v.pause();v.currentTime=stageEnd.current;stageEnd.current=null;}
    ctx.clearRect(0,0,c.width,c.height);
    const pose=result?frameAt(result.frames,v.currentTime):null;
    if(result&&overlay){
     if(pose){ctx.strokeStyle='#c2f77b';ctx.lineWidth=Math.max(2,c.width/420);ctx.lineCap='round';
      for(const[a,b]of BONES)if(pose.scores[a]>=.3&&pose.scores[b]>=.3){ctx.beginPath();ctx.moveTo(...pose.xy[a] as [number,number]);ctx.lineTo(...pose.xy[b] as [number,number]);ctx.stroke();}
      pose.xy.forEach(([x,y],i)=>{if(pose.scores[i]>=.3){ctx.fillStyle='#d3ff9b';ctx.beginPath();ctx.arc(x,y,c.width/230,0,Math.PI*2);ctx.fill();}});
     }
    }else if(!result&&editing){
     const [x1,y1,x2,y2]=crop.map((v,i)=>v*(i%2?c.height:c.width));
     ctx.fillStyle='rgba(6,24,20,.45)';ctx.beginPath();ctx.rect(0,0,c.width,c.height);ctx.rect(x1,y1,x2-x1,y2-y1);ctx.fill('evenodd');ctx.strokeStyle='#d3ff9b';ctx.lineWidth=3;ctx.strokeRect(x1,y1,x2-x1,y2-y1);
    }
    if(result&&referenceOverlay&&proVisible){
     const phase=referencePhaseAt(referenceOverlay.alignment,v.currentTime),tracked=frameAt(result.frames,v.currentTime);
     const referencePose=phase===null?null:referencePoseAt(referenceOverlay.poses,phase);
     const ghost=referencePose&&tracked?alignedReference(referencePose,tracked,referenceOverlay.fit):null;
     if(ghost){ctx.save();ctx.shadowColor='rgba(0,25,45,.9)';ctx.shadowBlur=3;ctx.strokeStyle='#66c9ff';ctx.fillStyle='#66c9ff';ctx.lineWidth=Math.max(3,c.width/330);ctx.setLineDash([c.width/150,c.width/250]);
      for(const[a,b]of REFERENCE_BONES){ctx.beginPath();ctx.moveTo(...ghost[a] as [number,number]);ctx.lineTo(...ghost[b] as [number,number]);ctx.stroke();}
      ctx.setLineDash([]);ghost.forEach(([x,y])=>{ctx.beginPath();ctx.arc(x,y,c.width/240,0,Math.PI*2);ctx.fill();});ctx.restore();
     }
    }
    const f=focusRef.current;
    if(pose&&focusVisible&&f&&v.currentTime>=f.start-.15&&v.currentTime<=f.end+.15){
     const pts=f.joints.filter(j=>pose.scores[j]>=.3).map(j=>pose.xy[j] as [number,number]);
     if(pts.length){
      const r=c.width/75,line=Math.max(2,c.width/520);ctx.save();ctx.lineWidth=line;ctx.strokeStyle='#ff9a62';ctx.fillStyle='rgba(255,154,98,.18)';
      for(const[x,y]of pts){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.stroke();}
      const anchor=pts.reduce((a,b)=>b[0]>a[0]?b:a),fs=Math.round(c.width/62),pad=fs*.55;
      ctx.font=`600 ${fs}px ui-sans-serif, system-ui, sans-serif`;const w=ctx.measureText(f.label).width+pad*2,h=fs+pad*1.2;
      let lx=anchor[0]+r*2.4,ly=anchor[1]-h/2;if(lx+w>c.width-8)lx=anchor[0]-r*2.4-w;ly=Math.max(8,Math.min(c.height-h-8,ly));
      ctx.beginPath();ctx.moveTo(anchor[0]+(lx>anchor[0]?r:-r),anchor[1]);ctx.lineTo(lx>anchor[0]?lx:lx+w,ly+h/2);ctx.stroke();
      ctx.fillStyle='#ff9a62';ctx.beginPath();ctx.roundRect(lx,ly,w,h,h/2);ctx.fill();ctx.fillStyle='#1d140e';ctx.textBaseline='middle';ctx.fillText(f.label,lx+pad,ly+h/2+1);ctx.restore();
     }
    }
   }
   frame=requestAnimationFrame(draw);
  }
  draw();return()=>cancelAnimationFrame(frame);
 },[result,overlay,crop,editing,referenceOverlay,proVisible,focusVisible,job?.meta?.duration]);
 function select(j:Job){stageEnd.current=null;setReferenceOverlay(null);setRate('1');setJob(j);setCrop(j.options?.crop||j.suggestedCrop||[.25,.05,.75,.98]);setView(j.options?.view||j.view||'rear');setHand(j.options?.handedness||'right');setTime(0);setPlaying(false);setActive('loading');setEditing(j.status==='ready'||j.status==='failed');setError('');}
 async function upload(file?:File,sample?:string){
  if(!file&&!sample)return;setError('');setUploading(true);
  try{const j=await api(`/api/clips?${sample?'sample='+sample:'name='+encodeURIComponent(file!.name)}`,{method:'POST',body:sample?undefined:file});openServe(j.id);}
  catch(e){setError((e as Error).message);}finally{setUploading(false);if(input.current)input.current.value='';}
 }
 async function processClip(){
  if(!job)return;setError('');video.current?.pause();setEditing(false);
  try{setJob(await api(`/api/jobs/${job.id}`,{method:'POST',body:JSON.stringify({crop,view,handedness:hand}),headers:{'Content-Type':'application/json'}}));}
  catch(e){setError((e as Error).message);setEditing(true);}
 }
 const changeReferenceOverlay=useCallback((next:ReferenceOverlay|null,play=false)=>{
  stageEnd.current=null;setReferenceOverlay(next);const v=video.current;
  if(!next){if(v)v.playbackRate=1;setRate('1');return;}
  setOverlay(true);
  if(play&&v){v.currentTime=next.alignment[0].time;stageEnd.current=next.alignment.at(-1)!.time;v.playbackRate=.25;setRate('.25');setTime(v.currentTime);v.play().catch(e=>setError(e.message));v.scrollIntoView({behavior:'smooth',block:'center'});}
 },[]);
 function replayStage(stage:Stage){const range=stagePlayback(stage,job?.meta?.duration||0),v=video.current;if(!range||!v)return;stageEnd.current=range.end;v.currentTime=range.start;v.playbackRate=range.rate;setRate('.25');setTime(range.start);setActive(stage.id);v.play().catch(e=>setError(e.message));v.scrollIntoView({behavior:'smooth',block:'center'});}
 function seek(t:number,marker=''){stageEnd.current=null;if(video.current){video.current.currentTime=t;video.current.pause();setTime(t);setActive(marker);}}
 function point(e:PointerEvent<HTMLCanvasElement>){const r=e.currentTarget.getBoundingClientRect();return[Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];}
 function drag(e:PointerEvent<HTMLCanvasElement>){if(!start.current)return;const p=point(e),s=start.current;setCrop([Math.min(s[0],p[0]),Math.min(s[1],p[1]),Math.max(s[0],p[0]),Math.max(s[1],p[1])]);}
 const moment=result?.events.find(e=>e.id===active)||result?.events[0];
 const handedness=job?.options?.handedness||'right',activeStage=result?.stages?.find(s=>s.id===active),activeFocus=activeStage?bodyFocus(activeStage.id,handedness):null;
 focusRef.current=activeFocus&&activeStage?.start!=null&&activeStage.end!=null?{joints:activeFocus.marks||activeFocus.joints,label:activeFocus.part,start:activeStage.start,end:activeStage.end}:null;
 const phaseScores=referenceOverlay?.phaseScores;
 return <main className={`coach-app ${jobId?'coach-review-page':'coach-record-page'}`}>
  {error&&<div className="error" role="alert">{error} {jobId&&<Link href="/">Back to recording</Link>}</div>}
  {!jobId?<>
   <LiveCapture onReview={openServe}/>
   <div className="coach-library">
    <details><summary>Recent serves <span>{recent.length}</span></summary><div className="coach-recent-list">{recent.length?recent.map(j=><Link key={j.id} href={`/serves/${j.id}`}><span>{j.name}<small>{j.status==='complete'?'Review ready':j.status==='ready'?'Ready to process':j.status}</small></span><span>↗</span></Link>):<p>Your recorded serves will appear here.</p>}</div></details>
    <details><summary>Upload a video or try a sample</summary><button className="primary" disabled={uploading} onClick={()=>input.current?.click()}>{uploading?'Preparing your video…':'Choose a video'} <span>↗</span></button><p className="small muted">MP4 or MOV · 0.5–20 seconds · up to 128 MB</p><div className="sample-list">{health?.samples.map(sample=><button key={sample.id} disabled={uploading} onClick={()=>upload(undefined,sample.id)}>{sample.name}<small>{sample.label}</small></button>)}</div></details>
   </div>
   <input ref={input} type="file" accept="video/*" className="file-input" aria-label="Upload serve video" onChange={e=>upload(e.target.files?.[0])}/>
  </>:!job?<div className="coach-loading" role="status">{error?'This serve could not be opened.':'Loading your serve…'}</div>:<>
   <div className="coach-review-nav"><Link href="/">← Record another serve</Link><span>{working?'Preparing your review':result?'Review ready':'Prepare your recording'}</span></div>
   <div className="coach-review-grid">
    <div className="coach-video-column">    <section className="viewer panel">
     <div className="panel-head"><div><span className="eyebrow">YOUR RECORDING</span><h2>{job?.name||'Your serve'}</h2></div>{job&&<button className="text-button" disabled={working||uploading} onClick={()=>input.current?.click()}>Upload another ↗</button>}</div>
       <div className="video-stage"><div className="video-frame" style={{'--video-ratio':(job.meta?.width||16)/(job.meta?.height||9),aspectRatio:`${job.meta?.width||16}/${job.meta?.height||9}`,maxWidth:job.meta?`min(100%, ${520*job.meta.width/job.meta.height}px)`:'100%'} as CSSProperties}>
        <video ref={video} key={job.id} src={`/api/jobs/${job.id}/video.mp4`} poster={`/api/jobs/${job.id}/poster.jpg`} playsInline preload="auto" onLoadedMetadata={e=>{const t=result?.events.find(x=>x.id==='loading')?.time||0;e.currentTarget.currentTime=t;e.currentTarget.playbackRate=result?.events.length ? .25 : 1;setRate(result?.events.length?'.25':'1');setTime(t);}} onTimeUpdate={e=>setTime(e.currentTarget.currentTime)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)}/>
        <canvas ref={canvas} width={job.meta?.width||1280} height={job.meta?.height||720} className={editing&&!result?'editable':''} aria-label={result?"Your movement and professional player overlay":"Draw the player selection box"} onPointerDown={e=>{if(!editing||result)return;video.current?.pause();start.current=point(e);e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={drag} onPointerUp={e=>{drag(e);start.current=null;}} onPointerCancel={()=>{start.current=null;}}/>
        {result?<div className="overlay-chips" role="group" aria-label="Overlays">
         <button aria-pressed={overlay} onClick={()=>setOverlay(!overlay)}><i className="you"/>You</button>
         {referenceOverlay&&<button aria-pressed={proVisible} onClick={()=>setProVisible(!proVisible)}><i className="pro"/>{referenceOverlay.player.split(' ').at(-1)}</button>}
         {result.stages?.length?<button aria-pressed={focusVisible} onClick={()=>setFocusVisible(!focusVisible)}><i className="focus"/>Focus</button>:null}
        </div>:<span className="video-badge">{editing?'SELECT YOUR PLAYER':'YOUR SERVE'}</span>}
       </div>{working&&<div className="processing"><div className="spinner"/><strong>{job.stage}</strong><span>This page will update when your review is ready.</span><progress max="100" value={job.progress||5}/></div>}</div>
       <div className="transport"><button aria-label={playing?'Pause video':'Play video'} onClick={()=>{const v=video.current;if(v){if(v.paused)v.play().catch(e=>setError(e.message));else v.pause();}}}>{playing?'Ⅱ':'▶'}</button><span>{clock(time)}</span>{result?.stages?.length?<span className="transport-total">/ {clock(job.meta?.duration||0)}{activeStage&&<b>{activeStage.label}</b>}</span>:<><input aria-label="Video position" type="range" min="0" max={job.meta?.duration||1} step=".01" value={time} onChange={e=>seek(+e.target.value)}/><span>{clock(job.meta?.duration||0)}</span></>}<select aria-label="Playback speed" value={rate} onChange={e=>{setRate(e.target.value);if(video.current)video.current.playbackRate=+e.target.value;}}><option value=".25">0.25×</option><option value=".5">0.5×</option><option value="1">1×</option></select></div>
       {result?(result.stages?.length?<ServeTimeline stages={result.stages} phaseScores={phaseScores} duration={job.meta?.duration||0} time={time} active={active} onSeek={t=>seek(t,active)} onReplay={replayStage}/>:<div className="overlay-row"><span>{referenceOverlay?`Green: you · Blue dashed: ${referenceOverlay.player} · hips aligned`:'Green joints: tracking score ≥ 0.3'}</span></div>):<div className="crop-guide"><span>↖ Drag a box around the server, including raised arms and feet.</span><button className="text-button" disabled={working} onClick={()=>{setCrop([0,0,1,1]);setEditing(true);}}>Full frame</button></div>}
     <input ref={input} id="video-upload" type="file" accept="video/*" className="file-input" aria-label="Upload serve video" onChange={e=>upload(e.target.files?.[0])}/>
     {result?(result.stages?.length?null:<div className="moments"><div className="section-label">MOMENTS TO REVIEW <span>BODY TRACKING ESTIMATES</span></div>{result.events.length?<div className="moment-list">{result.events.map((m,i)=><button key={m.id} className={`moment ${active===m.id?'active':''}`} onClick={()=>seek(m.time,m.id)}><span className="moment-number">0{i+1}</span><span><strong>{m.label}</strong><small>{clock(m.time)}</small></span><span>↗</span></button>)}</div>:<p className="muted">No reliable phase markers for this recording. You can still inspect the video and skeleton.</p>}{moment&&<p className="moment-detail">{moment.detail}</p>}</div>):<div className="sample-section"><div className="section-label">OR EXPLORE A SAMPLE <span>REAL RECORDINGS</span></div><div className="sample-list">{health?.samples.map((s,i)=><button key={s.id} disabled={uploading||working} onClick={()=>upload(undefined,s.id)}><span className="sample-number">0{i+1}</span><strong>{s.name}</strong><small>{s.label}</small><span className="sample-arrow">↗</span></button>)}</div></div>}
    </section>
</div>
    <aside className="coach-review-card">
     {result&&job.meta?<CoachComparison key={job.id} view={job.options?.view||job.view} handedness={job.options?.handedness||'unknown'} duration={job.meta.duration} events={result.events} frames={result.frames} stages={result.stages} onOverlayChange={changeReferenceOverlay}>
      <MovementInsight key={job.id} jobId={job.id} stages={result.stages||[]} active={active} handedness={handedness} onReplay={replayStage} onSelect={setActive} onSeek={t=>seek(t,active)}/>
      <Link className="primary coach-new-serve" href="/">Record another serve <span>↗</span></Link>
     </CoachComparison>:<div className="setup"><div className="setup-intro"><span className="outline-ball">↗</span><p>Upload one serve. Select yourself.<br/>We’ll track the movement and bring you back to the important frames.</p></div>
      <label className="field">Camera view<select value={view} disabled={working} onChange={e=>setView(e.target.value as Options['view'])}><option value="rear">Behind the server</option><option value="side">Side of the server</option><option value="front">Facing the server</option><option value="unknown">Not sure</option></select></label>
      <label className="field">Hitting hand<select value={hand} disabled={working} onChange={e=>setHand(e.target.value as Options['handedness'])}><option value="right">Right-handed</option><option value="left">Left-handed</option><option value="unknown">Not sure</option></select></label>
      <p className="small muted">Initial phase rules support right-handed serves from the side or rear. Other recordings remain available for visual review.</p>
      <button className="primary process" disabled={!job||working||uploading} onClick={processClip}>{working?'Processing your serve…':job?.status==='failed'?'Retry processing':'Process serve'}<span>↗</span></button>
      {job?.status==='failed'&&<div className="error" role="alert">{job.error}</div>}
      <div className="note"><span>ⓘ</span><p>Include the whole body, room above the hands, and the finish. Keep the camera still.</p></div>
      <div className="expect"><span className="eyebrow">WHAT YOU’LL GET</span><p><span>01</span> Your movement, tracked</p><p><span>02</span> Clickable serve moments</p><p><span>03</span> Feedback tied to visible evidence</p></div>
</div>}
     {result&&<details className="technical"><summary>Processing & evidence</summary><p>{result.stats.frames} frames sampled at {result.stats.sample_fps} fps · {result.stats.processing_seconds.toFixed(1)} seconds</p>{result.limitations.map(l=><p key={l}>{l}</p>)}<a href={`/api/jobs/${job.id}/result.json`} download>Download analysis JSON ↗</a></details>}
    </aside>
   </div>
  </>}
 </main>;
}
