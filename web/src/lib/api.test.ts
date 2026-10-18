import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';

test('upload -> persistent preview -> seek; invalid uploads and duplicate process requests fail',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'djoker-api-'));
 process.env.DJOKER_DATA_DIR=join(dir,'jobs');
 const clips=await import('../app/api/clips/route');
 const jobs=await import('../app/api/jobs/[id]/route');
 const media=await import('../app/api/jobs/[id]/[asset]/route');
 try {
  let r=await clips.POST(new Request('http://localhost/api/clips',{method:'POST',headers:{'content-length':String(129*1024*1024)}}));
  assert.equal(r.status,413);
  r=await clips.POST(new Request('http://localhost/api/clips',{method:'POST',body:'not a video'}));
  assert.equal(r.status,400);
  const path=join(dir,'fixture.mp4');
  execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','color=c=green:s=320x240:d=1','-c:v','libx264',path]);
  r=await clips.POST(new Request('http://localhost/api/clips?name=fixture.mp4',{method:'POST',body:await readFile(path)}));
  assert.equal(r.status,201,await r.clone().text());
  const job=await r.json();assert.equal(job.status,'ready');assert.equal(job.meta.width,320);
  const context={params:Promise.resolve({id:job.id,asset:'video.mp4'})};
  r=await media.GET(new Request('http://localhost/video',{headers:{range:'bytes=0-31'}}),context);
  assert.equal(r.status,206);assert.equal((await r.arrayBuffer()).byteLength,32);
  r=await media.GET(new Request('http://localhost/video'),{params:Promise.resolve({id:job.id,asset:'../../private'})});
  assert.equal(r.status,404);
  await writeFile(join(process.env.DJOKER_DATA_DIR!,job.id,'job.json'),JSON.stringify({...job,status:'processing'}));
  r=await jobs.POST(new Request('http://localhost/process',{method:'POST',body:JSON.stringify({crop:[0,0,1,1],view:'rear',handedness:'right'})}),{params:Promise.resolve({id:job.id})});
  assert.equal(r.status,409);
 } finally {await rm(dir,{recursive:true,force:true});}
});
