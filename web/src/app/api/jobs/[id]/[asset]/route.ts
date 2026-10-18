import {stat} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {Readable} from 'node:stream';
import {join} from 'node:path';
import {jobDir} from '@/lib/jobs';
import {parseRange} from '@/lib/contracts';
export const runtime='nodejs';
export const dynamic='force-dynamic';
type Ctx={params:Promise<{id:string;asset:string}>};
export async function GET(req:Request,ctx:Ctx) {
 const {id,asset}=await ctx.params;
 if(!['video.mp4','poster.jpg','result.json','runner.log'].includes(asset))return new Response(null,{status:404});
 try {
  const file=join(jobDir(id),asset),{size}=await stat(file),range=req.headers.get('range');
  let start=0,end=size-1;
  if(range){try{[start,end]=parseRange(range,size);}catch{return new Response(null,{status:416,headers:{'Content-Range':`bytes */${size}`}});}}
  const headers:Record<string,string>={'Content-Type':asset.endsWith('.mp4')?'video/mp4':asset.endsWith('.jpg')?'image/jpeg':asset.endsWith('.json')?'application/json':'text/plain',
   'Content-Length':String(end-start+1),'Accept-Ranges':'bytes','Cache-Control':'no-store'};
  if(range)headers['Content-Range']=`bytes ${start}-${end}/${size}`;
  return new Response(Readable.toWeb(createReadStream(file,{start,end})) as ReadableStream,{status:range?206:200,headers});
 }catch{return new Response(null,{status:404});}
}
