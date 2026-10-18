import {readFile,open,unlink} from 'node:fs/promises';
import {join} from 'node:path';
import {jobDir,loadJob,saveJob,launch} from '@/lib/jobs';
import {parseOptions} from '@/lib/contracts';
export const runtime='nodejs';
export const dynamic='force-dynamic';
type Ctx={params:Promise<{id:string}>};
export async function GET(_req:Request,ctx:Ctx) {
 try {const {id}=await ctx.params;const job=await loadJob(id);
  if(job.status==='complete')job.result=JSON.parse(await readFile(join(jobDir(id),'result.json'),'utf8'));
  return Response.json(job);
 }catch{return Response.json({error:'Serve not found.'},{status:404});}
}
export async function POST(req:Request,ctx:Ctx) {
 const {id}=await ctx.params;let lock:string|undefined;
 try {
  const options=parseOptions(await req.json());const job=await loadJob(id);
  if(!['ready','failed'].includes(job.status))return Response.json({error:'This serve is already processing or complete. Upload it again for another analysis.'},{status:409});
  const path=join(jobDir(id),'launch.lock');
  try {const f=await open(path,'wx');await f.close();lock=path;}catch{return Response.json({error:'A process request is already in progress.'},{status:409});}
  // A failed inference can leave temporary tensors. The worker replaces its own temporary folders on retry.
  await saveJob(id,{...job,options,status:'queued',stage:'Waiting for processor',error:null,progress:0});launch(id);
  return Response.json(await loadJob(id),{status:202});
 }catch(e){return Response.json({error:e instanceof Error?e.message:'Cannot start processing.'},{status:400});}
 finally {if(lock)await unlink(lock).catch(()=>{});}
}
