import {randomUUID} from 'node:crypto';
import {mkdir,open,copyFile,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {jobDir,saveJob,loadJob,prepare,listJobs,samplePath,samples} from '@/lib/jobs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const MAX=128*1024*1024;
export async function GET() {return Response.json(await listJobs());}
export async function POST(req:Request) {
 if(Number(req.headers.get('content-length')||0)>MAX)return Response.json({error:'Use a video under 128 MB.'},{status:413});
 const id=randomUUID(),dir=jobDir(id),url=new URL(req.url),sample=url.searchParams.get('sample');
 try {
  await mkdir(dir,{recursive:true});
  if(sample)await copyFile(samplePath(sample),join(dir,'input'));
  else {
   if(!req.body)throw Error('Choose a video to upload.');
   const file=await open(join(dir,'input'),'wx'),reader=req.body.getReader();let bytes=0;
   try {while(true){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>MAX)throw Error('Use a video under 128 MB.');await file.write(value);}}
   finally {await file.close();await reader.cancel();}
   if(!bytes)throw Error('The uploaded file is empty.');
  }
  const s=samples.find(s=>s.id===sample);
  await saveJob(id,{id,name:(s?.name || url.searchParams.get('name') || 'Your serve').slice(0,160),created:Date.now(),
    status:'preparing',stage:'Preparing playback',suggestedCrop:s?.crop,view:s?.view || 'rear'});
  try {await prepare(id);} catch {
   const failed=await loadJob(id);throw Error(failed.error || 'Could not decode this video. Try an MP4 or MOV file.');
  }
  return Response.json(await loadJob(id),{status:201});
 } catch(e) {
  await rm(dir,{recursive:true,force:true});
  const error=e instanceof Error?e.message:'Upload failed';
  return Response.json({error},{status:error.includes('128 MB')?413:400});
 }
}
