'use client';
import {useEffect,useRef,useState,PointerEvent} from 'react';
import {frameAt} from '@/lib/playback';
import type {Options} from '@/lib/contracts';

type Moment={id:string;label:string;time:number;detail:string};
type Result={events:Moment[];frames:{time:number;xy:number[][];scores:number[]}[];feedback:{mode:string;observation:string;suggestion:string|null;drill:string|null};stats:{frames:number;sample_fps:number;mean_inference_ms:number|null;processing_seconds:number;backend:string};limitations:string[]};
type Job={id:string;name:string;status:string;stage:string;created:number;progress?:number;error?:string;view:Options['view'];suggestedCrop?:number[];meta?:{width:number;height:number;duration:number};options?:Options;result?:Result};
type Sample={id:string;name:string;label:string};
const BONES=[[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
const clock=(n:number)=>`${Math.floor(n/60)}:${(n%60).toFixed(2).padStart(5,'0')}`;
async function api(url:string,init?:RequestInit){const r=await fetch(url,init);const data=await r.json();if(!r.ok)throw Error(data.error||'The request failed.');return data;}

export default function Home(){
 const [job,setJob]=useState<Job|null>(null),[recent,setRecent]=useState<Job[]>([]),[health,setHealth]=useState<{connected:boolean;cpu:boolean;python:boolean;samples:Sample[]}|null>(null);
 const [uploading,setUploading]=useState(false),[error,setError]=useState(''),[crop,setCrop]=useState([.25,.05,.75,.98]);
 const [view,setView]=useState<Options['view']>('rear'),[hand,setHand]=useState<Options['handedness']>('right');
 const [editing,setEditing]=useState(true),[overlay,setOverlay]=useState(true),[time,setTime]=useState(0),[playing,setPlaying]=useState(false),[active,setActive]=useState('');
 const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null),input=useRef<HTMLInputElement>(null),start=useRef<number[]|null>(null);
 const working=!!job&&['queued','processing','preparing'].includes(job.status),result=job?.result;
 const refresh=()=>api('/api/clips').then(setRecent).catch(()=>{});
 useEffect(()=>{const check=()=>api('/api/health').then(setHealth).catch(()=>{});check();refresh();const timer=setInterval(check,10000);return()=>clearInterval(timer);},[]);
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
    ctx.clearRect(0,0,c.width,c.height);
    if(result&&overlay){
     const pose=frameAt(result.frames,v.currentTime);
     if(pose){ctx.strokeStyle='#c2f77b';ctx.lineWidth=Math.max(2,c.width/420);ctx.lineCap='round';
      for(const[a,b]of BONES)if(pose.scores[a]>=.3&&pose.scores[b]>=.3){ctx.beginPath();ctx.moveTo(...pose.xy[a] as [number,number]);ctx.lineTo(...pose.xy[b] as [number,number]);ctx.stroke();}
      pose.xy.forEach(([x,y],i)=>{if(pose.scores[i]>=.3){ctx.fillStyle='#d3ff9b';ctx.beginPath();ctx.arc(x,y,c.width/230,0,Math.PI*2);ctx.fill();}});
     }
    }else if(!result&&editing){
     const [x1,y1,x2,y2]=crop.map((v,i)=>v*(i%2?c.height:c.width));
     ctx.fillStyle='rgba(6,24,20,.45)';ctx.beginPath();ctx.rect(0,0,c.width,c.height);ctx.rect(x1,y1,x2-x1,y2-y1);ctx.fill('evenodd');ctx.strokeStyle='#d3ff9b';ctx.lineWidth=3;ctx.strokeRect(x1,y1,x2-x1,y2-y1);
    }
   }
   frame=requestAnimationFrame(draw);
  }
  draw();return()=>cancelAnimationFrame(frame);
 },[result,overlay,crop,editing]);
 function select(j:Job){setJob(j);setCrop(j.options?.crop||j.suggestedCrop||[.25,.05,.75,.98]);setView(j.options?.view||j.view||'rear');setHand(j.options?.handedness||'right');setTime(0);setPlaying(false);setActive('');setEditing(j.status==='ready'||j.status==='failed');setError('');}
 async function upload(file?:File,sample?:string){
  if(!file&&!sample)return;setError('');setUploading(true);
  try{const j=await api(`/api/clips?${sample?'sample='+sample:'name='+encodeURIComponent(file!.name)}`,{method:'POST',body:sample?undefined:file});select(j);refresh();}
  catch(e){setError((e as Error).message);}finally{setUploading(false);if(input.current)input.current.value='';}
 }
 async function processClip(){
  if(!job)return;setError('');video.current?.pause();setEditing(false);
  try{setJob(await api(`/api/jobs/${job.id}`,{method:'POST',body:JSON.stringify({crop,view,handedness:hand}),headers:{'Content-Type':'application/json'}}));}
  catch(e){setError((e as Error).message);setEditing(true);}
 }
 function seek(t:number,marker=''){if(video.current){video.current.currentTime=t;video.current.pause();setTime(t);setActive(marker);}}
 function point(e:PointerEvent<HTMLCanvasElement>){const r=e.currentTarget.getBoundingClientRect();return[Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];}
 function drag(e:PointerEvent<HTMLCanvasElement>){if(!start.current)return;const p=point(e),s=start.current;setCrop([Math.min(s[0],p[0]),Math.min(s[1],p[1]),Math.max(s[0],p[0]),Math.max(s[1],p[1])]);}
 const moment=result?.events.find(e=>e.id===active)||result?.events[0];
 return <div className="shell">
  <aside className="sidebar">
   <a className="brand" href="/"><span className="brand-mark">◒</span> djoker<span className="brand-dot">.</span></a>
   <div className="workspace-label">YOUR PRACTICE SPACE</div>
   <button className="nav-item selected" disabled={working||uploading} onClick={()=>{setJob(null);setError('');}}><span>◷</span> Serve review <span className="nav-arrow">↗</span></button>
   <div className="recent-head">RECENT SERVES <span>{recent.length.toString().padStart(2,'0')}</span></div>
   <div className="recent-list">{recent.length?recent.map(j=><button key={j.id} className={`recent ${j.id===job?.id?'current':''}`} disabled={working||uploading} onClick={()=>api(`/api/jobs/${j.id}`).then(select).catch(e=>setError(e.message))}><span className={`small-dot ${j.status==='complete'?'green':''}`}/><span>{j.name}<small>{j.status==='complete'?'Review ready':j.status==='ready'?'Ready to process':j.status}</small></span></button>):<p className="muted small">Your reviewed serves will appear here.</p>}</div>
   <div className="sidebar-bottom"><div className="mini-ball">↗</div><p>One serve.<br/>One step forward.</p><small>Built for the practice court.</small></div>
  </aside>
  <main>
   <header className="topbar"><span>Practice / <strong>Serve review</strong></span><span className={`device ${health?.connected||health?.cpu?'online':''}`}><i/>{health?.connected?'Ventuno connected':health?.cpu?'Mac CPU available':'Processor unavailable'}</span></header>
   <div className="heading"><div><div className="eyebrow">LOOK CLOSER. PLAY BETTER.</div><h1>Your serve, frame by frame.</h1><p>Find the moments that matter. Build your next practice around them.</p></div><span className="version">SERVE LAB <b>01</b></span></div>
   <div className="steps"><span className={!job?'current':''}><b>01</b> Upload</span><i/><span className={job&&!result?'current':''}><b>02</b> Process</span><i/><span className={result?'current':''}><b>03</b> Review</span></div>
   {error&&<div className="error" role="alert">{error}</div>}
   <div className="review-grid">
    <section className="viewer panel">
     <div className="panel-head"><div><span className="eyebrow">YOUR RECORDING</span><h2>{job?.name||'Make your next serve count.'}</h2></div>{job&&<button className="text-button" disabled={working||uploading} onClick={()=>input.current?.click()}>Replace video ↗</button>}</div>
     {!job?<div className="drop-zone" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!uploading)upload(e.dataTransfer.files[0]);}}>
       <svg className="court-art" viewBox="0 0 600 350" aria-hidden="true"><path d="M135 330L205 35H395L465 330ZM170 185H430M192 90H408M300 90V285M145 285H455M220 35L190 330M380 35L410 330"/><circle cx="372" cy="112" r="13"/></svg>
       <div className="drop-content"><span className="upload-symbol">↥</span><h3>{uploading?'Preparing your recording…':'Start with a single serve.'}</h3><p>{uploading?'Getting your video ready for playback.':'Drop a video here, or choose one from your phone.'}</p><button className="primary light" disabled={uploading} onClick={()=>input.current?.click()}>{uploading?'Preparing…':'Choose a video'} <span>↗</span></button><small>MP4 or MOV · 0.5–20 seconds · up to 128 MB</small></div>
      </div>:<>
       <div className="video-stage"><div className="video-frame" style={{aspectRatio:`${job.meta?.width||16}/${job.meta?.height||9}`,maxWidth:job.meta?`min(100%, ${520*job.meta.width/job.meta.height}px)`:'100%'}}>
        <video ref={video} key={job.id} src={`/api/jobs/${job.id}/video.mp4`} poster={`/api/jobs/${job.id}/poster.jpg`} playsInline preload="auto" onTimeUpdate={e=>setTime(e.currentTarget.currentTime)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)}/>
        <canvas ref={canvas} width={job.meta?.width||1280} height={job.meta?.height||720} className={editing&&!result?'editable':''} aria-label="Draw the player selection box" onPointerDown={e=>{if(!editing||result)return;video.current?.pause();start.current=point(e);e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={drag} onPointerUp={e=>{drag(e);start.current=null;}} onPointerCancel={()=>{start.current=null;}}/>
        <span className="video-badge">{result?'POSE REVIEW':editing?'SELECT YOUR PLAYER':'YOUR SERVE'}</span>
       </div>{working&&<div className="processing"><div className="spinner"/><strong>{job.stage}</strong><span>This page will update when your review is ready.</span><progress max="100" value={job.progress||5}/></div>}</div>
       <div className="transport"><button aria-label={playing?'Pause video':'Play video'} onClick={()=>{const v=video.current;if(v){if(v.paused)v.play().catch(e=>setError(e.message));else v.pause();}}}>{playing?'Ⅱ':'▶'}</button><span>{clock(time)}</span><input aria-label="Video position" type="range" min="0" max={job.meta?.duration||1} step=".01" value={time} onChange={e=>seek(+e.target.value)}/><span>{clock(job.meta?.duration||0)}</span><select aria-label="Playback speed" defaultValue="1" onChange={e=>{if(video.current)video.current.playbackRate=+e.target.value;}}><option value=".25">0.25×</option><option value=".5">0.5×</option><option value="1">1×</option></select></div>
       {result?<div className="overlay-row"><label><input type="checkbox" checked={overlay} onChange={e=>setOverlay(e.target.checked)}/> Show skeleton</label><span>Green joints: tracking score ≥ 0.3</span></div>:<div className="crop-guide"><span>↖ Drag a box around the server, including raised arms and feet.</span><button className="text-button" disabled={working} onClick={()=>{setCrop([0,0,1,1]);setEditing(true);}}>Full frame</button></div>}
      </>}
     <input ref={input} id="video-upload" type="file" accept="video/*" className="file-input" aria-label="Upload serve video" onChange={e=>upload(e.target.files?.[0])}/>
     {result?<div className="moments"><div className="section-label">MOMENTS TO REVIEW <span>BODY TRACKING ESTIMATES</span></div>{result.events.length?<div className="moment-list">{result.events.map((m,i)=><button key={m.id} className={`moment ${active===m.id?'active':''}`} onClick={()=>seek(m.time,m.id)}><span className="moment-number">0{i+1}</span><span><strong>{m.label}</strong><small>{clock(m.time)}</small></span><span>↗</span></button>)}</div>:<p className="muted">No reliable phase markers for this recording. You can still inspect the video and skeleton.</p>}{moment&&<p className="moment-detail">{moment.detail}</p>}</div>:<div className="sample-section"><div className="section-label">OR EXPLORE A SAMPLE <span>REAL RECORDINGS</span></div><div className="sample-list">{health?.samples.map((s,i)=><button key={s.id} disabled={uploading||working} onClick={()=>upload(undefined,s.id)}><span className="sample-number">0{i+1}</span><strong>{s.name}</strong><small>{s.label}</small><span className="sample-arrow">↗</span></button>)}</div></div>}
    </section>
    <aside className="insight panel">
     <div className="panel-head"><div><span className="eyebrow">ONE STEP FORWARD</span><h2>{result?'Your review':'A clearer view of your serve.'}</h2></div><span className="insight-mark">✳</span></div>
     {result?<div className="feedback"><span className={`pill ${result.feedback.mode==='retry'?'amber':''}`}>{result.feedback.mode==='retry'?'A CLEARER RECORDING NEEDED':'OBSERVATION · NOT A TECHNIQUE SCORE'}</span><h3>{result.feedback.mode==='retry'?'Let’s get a better look.':'Start with your loading position.'}</h3><p className="observation">{result.feedback.observation}</p>
      {result.events.length>0&&<button className="primary" onClick={()=>seek(result.events[0].time,result.events[0].id)}>See the supporting frame <span>↗</span></button>}
      <div className="next-step"><span className="eyebrow">YOUR NEXT STEP</span><p>{result.feedback.suggestion||'Replay the loading moment, then the upward reach. Check that the skeleton follows your movement before using these measurements.'}</p></div>
      {result.feedback.drill&&<div className="next-step"><span className="eyebrow">PRACTICE DRILL</span><p>{result.feedback.drill}</p></div>}
      <div className="note"><span>ⓘ</span><p>{result.feedback.mode==='retry'?'No technique judgement was made.':'A correction is not supported yet. This version reports visible measurements and withholds unvalidated scores and drills.'}</p></div>
      <details className="technical"><summary>Processing & evidence</summary><dl><dt>Pose inference</dt><dd>{result.stats.backend}</dd><dt>Frames sampled</dt><dd>{result.stats.frames} at {result.stats.sample_fps} fps</dd><dt>Model time</dt><dd>{result.stats.mean_inference_ms?.toFixed(2)||'—'} ms / crop</dd><dt>Total processing</dt><dd>{result.stats.processing_seconds.toFixed(1)} seconds</dd></dl>{result.limitations.map(l=><p key={l}>{l}</p>)}<a href={`/api/jobs/${job!.id}/result.json`} download>Download analysis JSON ↗</a></details>
     </div>:<div className="setup"><div className="setup-intro"><span className="outline-ball">↗</span><p>Upload one serve. Select yourself.<br/>We’ll track the movement and bring you back to the important frames.</p></div>
      <label className="field">Camera view<select value={view} disabled={working} onChange={e=>setView(e.target.value as Options['view'])}><option value="rear">Behind the server</option><option value="side">Side of the server</option><option value="front">Facing the server</option><option value="unknown">Not sure</option></select></label>
      <label className="field">Hitting hand<select value={hand} disabled={working} onChange={e=>setHand(e.target.value as Options['handedness'])}><option value="right">Right-handed</option><option value="left">Left-handed</option><option value="unknown">Not sure</option></select></label>
      <p className="small muted">Initial phase rules support right-handed serves from the side or rear. Other recordings remain available for visual review.</p>
      <button className="primary process" disabled={!job||working||uploading} onClick={processClip}>{working?'Processing your serve…':job?.status==='failed'?'Retry processing':'Process serve'}<span>↗</span></button>
      {job?.status==='failed'&&<div className="error" role="alert">{job.error}</div>}
      <div className="note"><span>ⓘ</span><p>Include the whole body, room above the hands, and the finish. Keep the camera still.</p></div>
      <div className="expect"><span className="eyebrow">WHAT YOU’LL GET</span><p><span>01</span> Your movement, tracked</p><p><span>02</span> Clickable serve moments</p><p><span>03</span> Feedback tied to visible evidence</p></div>
     </div>}
    </aside>
   </div>
   <footer><span><i/> Processed locally. Your video stays on your devices.</span><span>Practice. Review. Repeat.</span></footer>
  </main>
 </div>;
}
