import {readFile,writeFile,mkdir,rmdir,unlink,rename} from 'node:fs/promises';
import {openSync,closeSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {DATA,ROOT,PYTHON} from '@/lib/jobs';
import {parseOptions} from '@/lib/contracts';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const dir=join(DATA,'live');
async function status(){
 try{
  const s=JSON.parse(await readFile(join(dir,'status.json'),'utf8'));
  if(s.active){try{if(!s.pid)throw Error();process.kill(s.pid,0);}catch{return {...s,active:false,state:'error',message:'Live capture stopped unexpectedly. Start it again.'};}}
  return s;
 }catch{return {active:false,state:'stopped',message:'Camera is off.'};}
}
export async function GET(){return Response.json(await status(),{headers:{'Cache-Control':'no-store'}});}
export async function POST(req:Request){
 const origin=req.headers.get('origin');
 const expectedOrigin=`${new URL(req.url).protocol}//${req.headers.get('host')||new URL(req.url).host}`;
 if(origin&&origin!==expectedOrigin)return Response.json({error:'Use the local Djoker page to control the camera.'},{status:403});
 let locked=false;
 try{
  const body=await req.json();
  if(!['start','stop','record','finish'].includes(body.action))throw Error('Choose start, stop, record or finish.');
  const mode=body.mode||'auto';
  if(!['continuous','auto','manual'].includes(mode))throw Error('Choose continuous, ready-gesture or manual capture.');
  const options=body.action==='start'?parseOptions(body.options):null;
  if(options&&(options.handedness!=='right'||!['rear','side'].includes(options.view)))throw Error('Automatic capture currently supports right-handed serves from the side or rear.');
  await mkdir(dir,{recursive:true});
  // Serialize controls through a short file-system mutex, including across dev reloads.
  try{await mkdir(join(dir,'control.lock'));locked=true;}catch{return Response.json({error:'Camera control is busy. Try again.'},{status:409});}
  const current=await status();
  if(body.action==='stop'){
   await writeFile(join(dir,'stop'),'stop');
   return Response.json({...current,message:current.active?'Stopping after the current processing step…':'Camera is off.'});
  }
  if(['record','finish'].includes(body.action)){
   if(!current.active||current.mode!=='manual'||current.state!==(body.action==='record'?'ready':'recording'))return Response.json({error:'The manual camera is not ready for this action.'},{status:409});
   const command=join(dir,'command.json');
   if(existsSync(command))return Response.json({error:'A recording command is already pending.'},{status:409});
   await writeFile(command+'.tmp',JSON.stringify({action:body.action}));
   await rename(command+'.tmp',command);
   return Response.json(current,{status:202});
  }
  if(current.active)return Response.json(current,{status:409});
  await unlink(join(dir,'command.json')).catch(()=>{});
  await unlink(join(dir,'stop')).catch(()=>{});
  const fd=openSync(join(dir,'worker.log'),'a');
  const child=spawn(/* turbopackIgnore: true */ PYTHON,[join(ROOT,'web/processor/live_capture.py'),DATA,JSON.stringify({...options,mode})],{detached:true,stdio:['ignore',fd,fd]});
  closeSync(fd);
  const started={mode,active:true,pid:child.pid,state:'starting',message:'Opening Ventuno camera…',updated:Date.now()/1000};
  await writeFile(join(dir,'status.json'),JSON.stringify(started));
  child.on('error',()=>{void writeFile(join(dir,'status.json'),JSON.stringify({active:false,state:'error',message:'Could not start live tracking. Check the configured Python environment.'}));});
  child.unref();
  return Response.json(started,{status:202});
 }catch(e){return Response.json({error:e instanceof Error?e.message:'Camera request failed.'},{status:400});}
 finally{if(locked)await rmdir(join(dir,'control.lock')).catch(()=>{});}
}
