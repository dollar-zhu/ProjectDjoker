import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {join} from 'node:path';
import {PYTHON,ROOT} from '@/lib/jobs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET(req:Request){
 const q=new URL(req.url).searchParams,player=q.get('player')||'djokovic',type=q.get('type')||'1',serve=q.get('serve');
 if(!['djokovic','sinner'].includes(player)||!['1','2'].includes(type)||(serve&&!/^[a-zA-Z0-9_-]+\.npy$/.test(serve)))return Response.json({error:'Invalid reference selection.'},{status:400});
 try{
  const args=[join(ROOT,'web/processor/reference_data.py'),player,type,...(serve?[serve]:[])];
  const {stdout}=await promisify(execFile)(/* turbopackIgnore: true */ PYTHON,args,{timeout:15000,maxBuffer:2*1024*1024});
  return Response.json(JSON.parse(stdout));
 }catch{return Response.json({error:'Reference unavailable. Check that the selected serve and dataset files exist.'},{status:422});}
}
