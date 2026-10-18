export const MAX_WAV_BYTES=320044;
export type AudioStatus={
 available:boolean;enabled:boolean;muted:boolean;listening:boolean;state:string;
 paired:boolean;connected:boolean;audio_ready:boolean;heart_ready?:boolean;updated:number;pid?:number;session?:string;
 transcript?:string;response?:string;observation_text?:string;error?:string;host?:string;led_error?:string;led_capability?:string;asr_error?:string;
 socket?:string;
};
export const unavailableAudio=(error='Audio worker is unavailable. Start the camera and check its audio configuration.'):AudioStatus=>({
 available:false,enabled:false,muted:true,listening:false,state:'DISABLED',paired:false,connected:false,audio_ready:false,heart_ready:false,updated:0,error,
});
export function validateStatus(audio:unknown,camera:unknown,now=Date.now()/1000,alive:(pid:number)=>boolean=()=>true):AudioStatus{
 if(!audio||typeof audio!=='object'||!camera||typeof camera!=='object')return unavailableAudio();
 const raw=audio as Record<string,unknown>,c=camera as Record<string,unknown>;
 const route=raw.route&&typeof raw.route==='object'?raw.route as Record<string,unknown>:{};
 const a:Record<string,unknown>={...raw,session:raw.session_id??raw.session,
  listening:raw.listening===undefined?raw.state==='LISTENING':raw.listening,
  paired:raw.paired===undefined?route.paired:raw.paired,connected:raw.connected===undefined?route.connected:raw.connected};
 if(c.active!==true||!Number.isInteger(a.pid)||(a.pid as number)<=0||a.pid!==c.pid||
  typeof a.session!=='string'||!a.session||a.session!==(c.session_id??c.session)||
  typeof a.updated!=='number'||!Number.isFinite(a.updated)||now-a.updated>5||a.updated>now+1||
  !alive(a.pid as number))return unavailableAudio('Audio status is stale or the camera session ended. Restart the camera.');
 if(['enabled','muted','listening','paired','connected','audio_ready'].some(k=>typeof a[k]!=='boolean')||typeof a.state!=='string')return unavailableAudio('Invalid audio worker status.');
 const result:AudioStatus={available:true,enabled:a.enabled as boolean,muted:a.muted as boolean,listening:a.listening as boolean,state:a.state,paired:a.paired as boolean,connected:a.connected as boolean,audio_ready:a.audio_ready as boolean,updated:a.updated,pid:a.pid as number,session:a.session};
 const heart=raw.heart&&typeof raw.heart==='object'?raw.heart as Record<string,unknown>:null;
 result.heart_ready=result.audio_ready&&(heart===null?true:heart.ready===true);
 for(const key of ['transcript','response','observation_text','error','host','led_error','led_capability'] as const)if(typeof a[key]==='string')result[key]=(a[key] as string).slice(0,4000);
 const asr=raw.asr&&typeof raw.asr==='object'?raw.asr as Record<string,unknown>:null;
 if(asr?.enabled===true&&typeof asr.error==='string')result.asr_error=asr.error.slice(0,4000);
 // The worker binds outside DATA when DATA/live/audio.sock would overflow sun_path.
 if(typeof raw.socket==='string'&&raw.socket.startsWith('/')&&raw.socket.endsWith('/audio.sock'))result.socket=raw.socket;
 return result;
}
export type AudioCommand={action:'enable'|'mute'|'cancel'|'listen'|'stop_listening'|'question';value?:boolean;text?:string};
export function parseAudioCommand(value:unknown):AudioCommand{
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Send an audio action object.');
 const b=value as Record<string,unknown>;
 if(Object.keys(b).some(k=>!['action','value','text'].includes(k))||!['enable','mute','cancel','listen','stop_listening','question'].includes(String(b.action)))throw Error('Unknown audio action.');
 if(b.action==='enable'||b.action==='mute'){
  if(typeof b.value!=='boolean'||b.text!==undefined)throw Error('Enable and mute require a boolean value.');
 }else if(b.action==='question'){
  if(typeof b.text!=='string'||!b.text.trim()||b.text.length>500||b.value!==undefined)throw Error('Enter a question of 1–500 characters.');
 }else if(b.value!==undefined||b.text!==undefined)throw Error('This action does not accept value or text.');
 return {action:b.action as AudioCommand['action'],...(typeof b.value==='boolean'?{value:b.value}:{}),...(typeof b.text==='string'?{text:b.text.trim()}:{})};
}
export function canUploadAudio(s:AudioStatus){return s.available&&s.enabled&&!s.muted&&s.listening&&s.state!=='SPEAKING';}
export async function readBounded(req:Request,max:number):Promise<Uint8Array>{
 const length=req.headers.get('content-length');
 if(length!==null&&(!/^\d+$/.test(length)||Number(length)>max))throw Error('Request body is too large.');
 if(!req.body)throw Error('Request body is empty.');
 const reader=req.body.getReader(),chunks:Uint8Array[]=[];let size=0;
 try{
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
   if(size>max){await reader.cancel();throw Error('Request body is too large.');}chunks.push(value);
  }
 }finally{reader.releaseLock();}
 const out=new Uint8Array(size);let offset=0;for(const chunk of chunks){out.set(chunk,offset);offset+=chunk.length;}return out;
}
export function validateWav(bytes:Uint8Array){
 const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 const tag=(offset:number)=>String.fromCharCode(...bytes.subarray(offset,offset+4));
 if(bytes.length<46||bytes.length>MAX_WAV_BYTES||tag(0)!=='RIFF'||tag(8)!=='WAVE'||tag(12)!=='fmt '||
  v.getUint32(4,true)!==bytes.length-8||v.getUint32(16,true)!==16||v.getUint16(20,true)!==1||
  v.getUint16(22,true)!==1||v.getUint32(24,true)!==16000||v.getUint32(28,true)!==32000||
  v.getUint16(32,true)!==2||v.getUint16(34,true)!==16||tag(36)!=='data'||
  v.getUint32(40,true)!==bytes.length-44||(bytes.length-44)%2!==0)throw Error('Use mono PCM16 WAV at 16 kHz, at most 10 seconds.');
}
