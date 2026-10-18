import {readFile,mkdir,rmdir,writeFile,rename,unlink,access} from 'node:fs/promises';
import {join} from 'node:path';
import {createConnection} from 'node:net';
import {DATA} from '@/lib/jobs';
import {canUploadAudio,MAX_WAV_BYTES,parseAudioCommand,readBounded,unavailableAudio,validateStatus,validateWav} from '@/lib/live-audio';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const dir=join(DATA,'live');
async function status(){
 try{
  const [audio,camera]=await Promise.all(['audio-status.json','status.json'].map(async name=>JSON.parse(await readFile(join(dir,name),'utf8'))));
  return validateStatus(audio,camera,Date.now()/1000,pid=>{try{process.kill(pid,0);return true;}catch{return false;}});
 }catch{return unavailableAudio();}
}
export async function GET(){const {socket:_,...pub}=await status();return Response.json(pub,{headers:{'Cache-Control':'no-store'}});}
async function exists(path:string){try{await access(path);return true;}catch{return false;}}
async function sendWav(bytes:Uint8Array,session:string,path=join(dir,'audio.sock')){
 await new Promise<void>((resolve,reject)=>{
  const socket=createConnection(path);
  let ack=Buffer.alloc(0),settled=false;
  const finish=(error?:Error)=>{
   if(settled)return;settled=true;clearTimeout(timer);socket.destroy();
   if(error)reject(error);else resolve();
  };
  const parse=()=>{
   try{
    const result=JSON.parse(ack.toString('utf8').split('\n')[0]);
    if(result.accepted!==true)throw Error(typeof result.error==='string'?result.error.slice(0,500):'Audio worker rejected the utterance.');
    finish();
   }catch(e){finish(e instanceof Error?e:Error('Invalid audio worker acknowledgment.'));}
  };
  const timer=setTimeout(()=>finish(Error('Audio worker did not respond within 2 seconds. Check its audio configuration.')),2000);
  socket.once('connect',()=>{socket.write(JSON.stringify({session_id:session,length:bytes.length})+'\n');socket.write(bytes);});
  socket.on('data',chunk=>{
   if(ack.length+chunk.length>1024){finish(Error('Audio worker acknowledgment is too large.'));return;}
   ack=Buffer.concat([ack,chunk]);if(ack.includes(10))parse();
  });
  socket.once('end',()=>{if(!settled)parse();});
  socket.once('error',()=>finish(Error('Audio worker socket is unavailable. Restart the camera and check the worker configuration.')));
  socket.once('close',()=>{if(!settled)finish(Error('Audio worker disconnected without acknowledging the utterance.'));});
 });
}
export async function POST(req:Request){
 const url=new URL(req.url),origin=req.headers.get('origin');
 if(origin&&origin!==`${url.protocol}//${req.headers.get('host')||url.host}`)return Response.json({error:'Use the local Djoker page to control audio.'},{status:403});
 const type=req.headers.get('content-type')?.split(';')[0].trim().toLowerCase();
 if(type!=='application/json'&&type!=='audio/wav')return Response.json({error:'Send application/json or audio/wav.'},{status:415});
 let locked=false,tmp:string|undefined;
 try{
  const bytes=await readBounded(req,type==='audio/wav'?MAX_WAV_BYTES:4096);
  const command=type==='application/json'?parseAudioCommand(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes))):null;
  if(!command)validateWav(bytes);
  await mkdir(dir,{recursive:true});
  try{await mkdir(join(dir,'audio-control.lock'));locked=true;}catch{return Response.json({error:'Audio control is busy. Try again.'},{status:409});}
  const current=await status();
  if(!current.available)return Response.json({error:current.error},{status:409});
  if(!command&&!canUploadAudio(current))return Response.json({error:'Hold to talk only while listening, enabled and unmuted. Wait for speech to finish.'},{status:409});
  if(command&&['listen','question'].includes(command.action)&&(!current.enabled||current.muted||current.state==='SPEAKING'))return Response.json({error:'Enable and unmute audio, then wait for speech to finish.'},{status:409});
  const path=join(dir,'audio-command.json');
  if(await exists(path))return Response.json({error:'An audio request is pending. Wait and try again.'},{status:409});
  if(command){
   tmp=path+'.node.tmp';
   await writeFile(tmp,JSON.stringify({...command,pid:current.pid,session_id:current.session}),{flag:'wx',mode:0o600});
  }
  const latest=await status();
  if(!latest.available||latest.session!==current.session||latest.pid!==current.pid||(!command&&!canUploadAudio(latest)))return Response.json({error:'Audio session changed. Try again.'},{status:409});
  if(command){await rename(tmp!,path);tmp=undefined;}
  else await sendWav(bytes,current.session!,current.socket);
  return Response.json({accepted:true},{status:202});
 }catch(e){
  const error=e instanceof Error?e.message:'Audio request failed.';
  return Response.json({error},{status:error==='Request body is too large.'?413:400});
 }finally{
  if(tmp)await unlink(tmp).catch(()=>{});
  if(locked)await rmdir(join(dir,'audio-control.lock')).catch(()=>{});
 }
}
