import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

test('live API rejects unsupported automatic capture and foreign origins; stale processes are inactive',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'djoker-live-'));
 process.env.DJOKER_DATA_DIR=dir;
 const route=await import('../app/api/live/route');
 try {
  let r=await route.POST(new Request('http://localhost/api/live',{method:'POST',headers:{Origin:'https://example.com'},body:JSON.stringify({action:'stop'})}));
  assert.equal(r.status,403);
  r=await route.POST(new Request('http://localhost:3017/api/live',{method:'POST',headers:{Origin:'http://127.0.0.1:3017',Host:'127.0.0.1:3017'},body:JSON.stringify({action:'stop'})}));
  assert.equal(r.status,200, 'Next can normalize req.url; match the actual Host header');
  for(const options of [{crop:[0,0,1,1],view:'rear',handedness:'unknown'},{crop:[0,0,1,1],view:'front',handedness:'right'},{crop:[0,0,0,0],view:'rear',handedness:'right'}]){
   r=await route.POST(new Request('http://localhost/api/live',{method:'POST',body:JSON.stringify({action:'start',options})}));
   assert.equal(r.status,400);
  }
  await mkdir(join(dir,'live'),{recursive:true});
  await writeFile(join(dir,'live/status.json'),JSON.stringify({active:true,pid:process.pid,state:'ready',mode:'manual'}));
  r=await route.POST(new Request('http://localhost/api/live',{method:'POST',body:JSON.stringify({action:'record'})}));
  assert.equal(r.status,202);
  assert.equal(JSON.parse(await (await import('node:fs/promises')).readFile(join(dir,'live/command.json'),'utf8')).action,'record');
  r=await route.POST(new Request('http://localhost/api/live',{method:'POST',body:JSON.stringify({action:'record'})}));
  assert.equal(r.status,409,'Do not queue duplicate manual controls');
  await rm(join(dir,'live/command.json'));
  await writeFile(join(dir,'live/status.json'),JSON.stringify({active:true,pid:process.pid,state:'recording',mode:'manual'}));
  r=await route.POST(new Request('http://localhost/api/live',{method:'POST',body:JSON.stringify({action:'finish'})}));
  assert.equal(r.status,202);
  await rm(join(dir,'live/command.json'));
  await writeFile(join(dir,'live/status.json'),JSON.stringify({active:true,pid:2147483647,state:'recording'}));
  const state=await (await route.GET()).json();
  assert.equal(state.active,false);
  assert.equal(state.state,'error');
  const frames=await import('../app/api/live/frame/route');
  await writeFile(join(dir,'live/preview.jpg'),Buffer.from([255,216,1,255,217]));
  const stream=await frames.GET(new Request('http://localhost/api/live/frame?stream=1'));
  assert.match(stream.headers.get('content-type')||'',/multipart\/x-mixed-replace/);
  const reader=stream.body!.getReader();
  const first=await reader.read();
  assert.match(Buffer.from(first.value!).toString(),/Content-Length: 5/);
  await writeFile(join(dir,'live/preview.jpg'),Buffer.from([255,216,2,3,255,217]));
  const second=await reader.read();
  assert.match(Buffer.from(second.value!).toString(),/Content-Length: 6/);
  await reader.cancel();
 } finally {await rm(dir,{recursive:true,force:true});}
});
