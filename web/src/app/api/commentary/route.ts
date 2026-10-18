import {spawn} from 'node:child_process';
import {join} from 'node:path';
import {readFile} from 'node:fs/promises';
import {PYTHON,ROOT,jobDir,loadJob} from '@/lib/jobs';
import {validId} from '@/lib/contracts';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function POST(req:Request){
 const origin=req.headers.get('origin');const expectedOrigin=`${new URL(req.url).protocol}//${req.headers.get('host')||new URL(req.url).host}`;if(origin&&origin!==expectedOrigin)return Response.json({error:'Origin mismatch.'},{status:403});
 if(Number(req.headers.get('content-length')||0)>4096)return Response.json({error:'Request too large.'},{status:413});
 try{
  const raw=await req.text();if(raw.length>4096)throw Error('Request too large');
  const e=JSON.parse(raw);
  if(!e||typeof e!=='object'||Array.isArray(e))return Response.json({error:'Invalid request.'},{status:400});
  const args=[join(ROOT,'web/processor/commentary.py')];
  if('jobId' in e){
   if(Object.keys(e).length!==1||typeof e.jobId!=='string'||!validId(e.jobId))return Response.json({error:'Invalid job id.'},{status:400});
   let job;try{job=await loadJob(e.jobId);}catch{return Response.json({error:'Serve not found.'},{status:404});}
   if(job.status!=='complete')return Response.json({error:'Wait for pose analysis to finish.'},{status:409});
   const path=join(jobDir(e.jobId),'result.json');JSON.parse(await readFile(path,'utf8'));
   args.push(path);
  }else if(!['Novak Djokovic','Jannik Sinner'].includes(e.player)||!['time','userLeft','userRight','referenceLeft','referenceRight'].every(k=>typeof e[k]==='number'&&Number.isFinite(e[k])&&e[k]>=0&&e[k]<=180)||e.time<=0||e.time>=20)return Response.json({error:'Invalid comparison evidence.'},{status:400});
  const output=await new Promise<string>((resolve,reject)=>{
   const child=spawn(/* turbopackIgnore: true */ PYTHON,args,{stdio:['pipe','pipe','pipe']});
   let out='',err='';const timer=setTimeout(()=>{child.kill();reject(Error('Commentary timed out'));},140000);
   child.stdout.on('data',d=>{out+=d;if(out.length>1024*1024)child.kill();});child.stderr.on('data',d=>{err=(err+d).slice(-2000);});
   child.on('error',e=>{clearTimeout(timer);reject(e);});child.on('close',code=>{clearTimeout(timer);code===0?resolve(out):reject(Error(err||'Commentary failed'));});child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(e));
  });
  return Response.json(JSON.parse(output));
 }catch{return Response.json({error:'Commentary is unavailable. The overlay and measured comparison still work.'},{status:503});}
}
