'use client';
import {useEffect,useRef,useState} from 'react';
import {canUploadAudio,unavailableAudio,type AudioStatus,type AudioCommand} from '@/lib/live-audio';

function wav(samples:Float32Array,rate:number){
 const count=Math.min(160000,Math.floor(samples.length*16000/rate)),out=new ArrayBuffer(44+count*2),v=new DataView(out);
 const text=(at:number,s:string)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};
 text(0,'RIFF');v.setUint32(4,out.byteLength-8,true);text(8,'WAVE');text(12,'fmt ');v.setUint32(16,16,true);
 v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);
 v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,count*2,true);
 // Average source samples over each output interval to downsample browser-native rates.
 for(let i=0;i<count;i++){
  const start=Math.floor(i*rate/16000),end=Math.min(samples.length,Math.max(start+1,Math.floor((i+1)*rate/16000)));
  let sum=0;for(let j=start;j<end;j++)sum+=samples[j];
  const value=Math.max(-1,Math.min(1,sum/(end-start)));v.setInt16(44+i*2,Math.round(value*(value<0?32768:32767)),true);
 }
 return out;
}
type Recording={stream:MediaStream;context:AudioContext;source:MediaStreamAudioSourceNode;processor:ScriptProcessorNode;silence:GainNode;chunks:Float32Array[];count:number;timer?:ReturnType<typeof setTimeout>};
const RECORD_SECONDS=8;
export function LiveAudio({active}:{active:boolean}){
 const [status,setStatus]=useState<AudioStatus>(unavailableAudio()),[error,setError]=useState(''),[recording,setRecording]=useState(false),[question,setQuestion]=useState('');
 const statusRef=useRef(status),activeRef=useRef(active),mounted=useRef(true),held=useRef(false),generation=useRef(0),rec=useRef<Recording|null>(null);
 const [working,setWorking]=useState(false);
 activeRef.current=active;statusRef.current=status;
 async function command(body:AudioCommand){
  const r=await fetch('/api/live/audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await r.json();if(!r.ok)throw Error(result.error||'Audio request failed. Try again.');
 }
 function dispose(){
  const current=rec.current;rec.current=null;
  if(current){clearTimeout(current.timer);current.processor.onaudioprocess=null;current.source.disconnect();current.processor.disconnect();current.silence.disconnect();current.stream.getTracks().forEach(t=>t.stop());void current.context.close().catch(()=>{});}
  if(mounted.current)setRecording(false);
  return current;
 }
 function abort(notify=true){
  const wasHeld=held.current;
  held.current=false;generation.current++;const current=dispose();
  if((current||wasHeld)&&notify)void command({action:'stop_listening'}).catch(()=>{});
 }
 async function release(){
  if(!held.current)return;
  held.current=false;const token=++generation.current;const current=dispose();
  if(!current){void command({action:'stop_listening'}).catch(()=>{});return;}
  setWorking(true);
  let submitted=false;
  try{
   if(!activeRef.current)return;
   const fresh=await fetch('/api/live/audio',{cache:'no-store'});
   if(!fresh.ok)throw Error('Could not check listening state. Check the audio worker and retry.');
   const latest:AudioStatus=await fresh.json();
   if(!activeRef.current||!mounted.current||token!==generation.current)return;
   if(!canUploadAudio(latest))throw Error('Voice is not listening. Enable and unmute audio, wait for speech to finish, and hold to talk again.');
   if(!current.count)throw Error('No microphone samples captured. Hold to talk a little longer.');
   const samples=new Float32Array(current.count);let offset=0;
   for(const chunk of current.chunks){samples.set(chunk,offset);offset+=chunk.length;}
   const r=await fetch('/api/live/audio',{method:'POST',headers:{'Content-Type':'audio/wav'},body:wav(samples,current.context.sampleRate)});
   const result=await r.json();if(!r.ok)throw Error(result.error||'Could not send speech. Try again.');
   submitted=true;
  }catch(e){if(mounted.current)setError((e as Error).message);}
  finally{if(!submitted)void command({action:'stop_listening'}).catch(()=>{});if(mounted.current)setWorking(false);}
 }
 async function start(){
  if(held.current||!activeRef.current||!statusRef.current.available||!statusRef.current.enabled||statusRef.current.muted||statusRef.current.state==='SPEAKING')return;
  held.current=true;const token=++generation.current;setError('');
  let stream:MediaStream|undefined,context:AudioContext|undefined;
  try{
   if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone requires HTTPS or localhost and browser microphone permission.');
   stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
   if(token!==generation.current||!held.current||!activeRef.current){stream.getTracks().forEach(t=>t.stop());return;}
   context=new AudioContext();await context.resume();
   if(token!==generation.current||!held.current||!activeRef.current){stream.getTracks().forEach(t=>t.stop());await context.close();return;}
   await command({action:'listen'});
   if(token!==generation.current||!held.current||!activeRef.current){stream.getTracks().forEach(t=>t.stop());await context.close();void command({action:'stop_listening'}).catch(()=>{});return;}
   const source=context.createMediaStreamSource(stream),processor=context.createScriptProcessor(4096,1,1),silence=context.createGain();
   silence.gain.value=0;
   const current:Recording={stream,context,source,processor,silence,chunks:[],count:0};rec.current=current;
   processor.onaudioprocess=e=>{
    const remaining=Math.max(0,Math.floor(context!.sampleRate*RECORD_SECONDS)-current.count);
    if(remaining){const data=e.inputBuffer.getChannelData(0).slice(0,remaining);current.chunks.push(data);current.count+=data.length;}
    if(current.count>=context!.sampleRate*RECORD_SECONDS)void release();
   };
   source.connect(processor);processor.connect(silence);silence.connect(context.destination);
   current.timer=setTimeout(()=>void release(),RECORD_SECONDS*1000);setRecording(true);
  }catch(e){
   stream?.getTracks().forEach(t=>t.stop());if(context)void context.close().catch(()=>{});abort();
   void command({action:'stop_listening'}).catch(()=>{});
   if(mounted.current)setError(`Microphone unavailable: ${(e as Error).message}. Check browser permission and try again; camera capture is unchanged.`);
  }
 }
 useEffect(()=>{
  mounted.current=true;
  return()=>{mounted.current=false;abort();};
 // Recording lifecycle deliberately uses refs rather than retaining stale render state.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[]);
 useEffect(()=>{
  if(!active){abort();setStatus(unavailableAudio('Start the camera to connect audio.'));return;}
  let ended=false,timer:ReturnType<typeof setTimeout>;
  async function poll(){
   try{
    const r=await fetch('/api/live/audio',{cache:'no-store'});if(!r.ok)throw Error('Could not read audio status. Check the worker and retry.');
    const next:AudioStatus=await r.json();
    if(!ended){statusRef.current=next;setStatus(next);if(!next.available||!next.enabled||next.muted||next.state==='SPEAKING')abort();}
   }catch(e){if(!ended){statusRef.current=unavailableAudio((e as Error).message);setStatus(statusRef.current);abort();}}
   if(!ended)timer=setTimeout(poll,500);
  }
  void poll();return()=>{ended=true;clearTimeout(timer);abort();};
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[active]);
 async function control(body:AudioCommand){
  setError('');setWorking(true);
  if(body.action==='cancel'||body.action==='mute'||(body.action==='enable'&&!body.value))abort(false);
  try{await command(body);}catch(e){setError((e as Error).message);}finally{if(mounted.current)setWorking(false);}
 }
 const ready=active&&status.available,canTalk=ready&&status.enabled&&!status.muted&&status.state!=='SPEAKING'&&!working;
 const voiceState=!active?'Start the camera to connect voice.':!ready?'Connecting to voice…':!status.enabled?'Enable voice for spoken guidance.':status.muted?'Voice is muted.':!status.audio_ready?'Connect your configured headphones.':status.state==='SPEAKING'?'Coach is speaking…':status.state==='LISTENING'?'Listening… release to send.':['THINKING','TRANSCRIBING'].includes(status.state)?'Preparing your reply…':'Ready to coach.';
 return <section className="coach-voice" aria-label="Live voice controls">
  <div className="coach-voice-heading"><h3>Voice coach</h3><span role="img" aria-label={status.heart_ready?'Browser heart: audio ready':'Browser heart: audio not ready'} style={{color:status.heart_ready?'#ec4899':'#9b625b'}}>♥</span></div>
  <p className="coach-voice-status" role="status">{voiceState}</p>
  {status.led_error&&<p role="alert" className="error">Hardware indicator: {status.led_error} Check the optional LED backend and board connection; camera capture remains available.</p>}
  {status.asr_error&&<p role="alert" className="error">Speech recognition: {status.asr_error} Check the configured ASR runtime on the Python worker host, or use a typed question. Camera capture is unchanged.</p>}
  <div className="coach-voice-actions"><label className="coach-voice-toggle"><input type="checkbox" checked={status.enabled} disabled={!ready||working} onChange={e=>void control({action:'enable',value:e.target.checked})}/> Enable voice</label>
  <button type="button" disabled={!ready||working} onClick={()=>void control({action:'mute',value:!status.muted})}>{status.muted?'Unmute':'Mute'}</button>
  <button type="button" disabled={!ready} onClick={()=>void control({action:'cancel'})}>Cancel speech</button></div>
  <button className="coach-voice-talk" type="button" disabled={!canTalk&&!recording} style={{touchAction:'none'}} aria-pressed={recording}
   onPointerDown={e=>{if(e.button!==0)return;e.currentTarget.setPointerCapture(e.pointerId);void start();}}
   onPointerUp={()=>void release()} onPointerCancel={()=>abort()} onLostPointerCapture={()=>{if(held.current)abort();}}
   onKeyDown={e=>{if((e.key===' '||e.key==='Enter')&&!e.repeat){e.preventDefault();void start();}}}
   onKeyUp={e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();void release();}}} onBlur={()=>abort()}>
   {recording?`Release to send · ${RECORD_SECONDS} seconds maximum`:`Hold to talk · ${RECORD_SECONDS} seconds maximum`}
  </button>
  <form className="coach-voice-question" onSubmit={e=>{e.preventDefault();if(question.trim())void control({action:'question',text:question});}}>
   <label className="field">Ask the coach<input placeholder="What should I focus on?" value={question} maxLength={500} disabled={!canTalk} onChange={e=>setQuestion(e.target.value)}/></label>
   <button type="submit" disabled={!canTalk||!question.trim()}>Send question</button>
  </form>
  {status.observation_text&&<p role="status"><strong>Live observation:</strong> {status.observation_text}</p>}
  {status.transcript&&<p><strong>You:</strong> {status.transcript}</p>}
  {status.response&&<p><strong>Coach:</strong> {status.response}</p>}
  {(error||(active&&status.error))&&<p role="alert" className="error">{error||status.error}</p>}
  <details className="coach-voice-details"><summary>Voice setup & diagnostics</summary>
   <p>Playback uses your configured headphones on the worker or the connected Ventuno audio service. Hold to talk for up to {RECORD_SECONDS} seconds, then release. Wait for speech to finish before talking.</p>
   <p>{status.paired?'Paired':'Not paired'} · {status.connected?'Connected':'Disconnected'} · {status.audio_ready?'Audio ready':'Audio not ready'}{status.host?` · Worker: ${status.host}`:''}</p>
   <p>The heart shows audio readiness in this browser. Indicator: {status.led_capability||'browser'}. The optional board matrix is blue monochrome.</p>
  </details>
 </section>;
}
