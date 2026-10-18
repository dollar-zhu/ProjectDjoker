import {readFile,stat} from 'node:fs/promises';
import {join} from 'node:path';
import {DATA} from '@/lib/jobs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET(req:Request){
 const path=join(DATA,'live','preview.jpg');
 if(new URL(req.url).searchParams.get('stream')!=='1'){
  try{return new Response(await readFile(path),{headers:{'Content-Type':'image/jpeg','Cache-Control':'no-store'}});}
  catch{return new Response(null,{status:404});}
 }
 let stopped=false,last=0;
 const stream=new ReadableStream<Uint8Array>({
  async pull(controller){
   while(!stopped&&!req.signal.aborted){
    try{
     const info=await stat(path);
     if(info.mtimeMs!==last){
      const jpeg=await readFile(path);last=info.mtimeMs;
      controller.enqueue(Buffer.concat([Buffer.from(`--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${jpeg.length}\r\n\r\n`),jpeg,Buffer.from('\r\n')]));
      return;
     }
    }catch{/* The first preview may still be preparing. */}
    await new Promise(resolve=>setTimeout(resolve,33));
   }
   if(!stopped)controller.close();
  },
  cancel(){stopped=true;},
 },{highWaterMark:0});
 return new Response(stream,{headers:{'Content-Type':'multipart/x-mixed-replace; boundary=frame','Cache-Control':'no-store, no-transform','X-Accel-Buffering':'no'}});
}
