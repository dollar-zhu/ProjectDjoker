import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir,readFile,rm,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {createServer} from 'node:net';
import {canUploadAudio,MAX_WAV_BYTES,parseAudioCommand,readBounded,validateStatus,validateWav} from './live-audio';

const camera={active:true,pid:process.pid,session:'test-session'};
const audio={...camera,updated:100,enabled:true,muted:false,listening:true,state:'LISTENING',paired:true,connected:true,audio_ready:true};
function wav(){
 const b=Buffer.alloc(46);b.write('RIFF');b.writeUInt32LE(38,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);
 b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(16000,24);b.writeUInt32LE(32000,28);
 b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(2,40);return b;
}
test('audio status fails closed on stale, dead, mismatched, missing or invalid sessions',()=>{
 assert.equal(canUploadAudio(validateStatus(audio,camera,105,()=>true)),true);
 const {session,listening,paired,connected,...snapshot}=audio;
 assert.equal(canUploadAudio(validateStatus({...snapshot,session_id:session,route:{paired,connected}},{...camera,session_id:session},100)),true);
 for(const [a,c] of [
  [{...audio,updated:99},camera],[{...audio,updated:107},camera],[audio,{...camera,active:false}],
  [{...audio,pid:0},camera],[{...audio,session:'old'},camera],[{...audio,session:undefined},camera],
  [{...audio,updated:NaN},camera],[{...audio,muted:'false'},camera],[audio,{...camera,pid:42}],
 ]){
  const status=validateStatus(a,c,105,()=>true);assert.equal(status.available,false);assert.equal(status.enabled,false);assert.equal(canUploadAudio(status),false);
 }
 assert.equal(validateStatus(audio,camera,100,()=>false).available,false);
 for(const change of [{muted:true},{enabled:false},{listening:false},{state:'SPEAKING'}]){
  assert.equal(canUploadAudio(validateStatus({...audio,...change},camera,100)),false);
 }
});
test('commands strictly validate booleans, action fields, and 500-character question limit',()=>{
 assert.deepEqual(parseAudioCommand({action:'enable',value:false}),{action:'enable',value:false});
 assert.equal(parseAudioCommand({action:'question',text:'q'.repeat(500)}).text?.length,500);
 for(const value of [null,[],{action:'unknown'},{action:'mute',value:'false'},{action:'enable'},{action:'cancel',value:true},{action:'listen',text:'x'},{action:'question',text:' '},{action:'question',text:'q'.repeat(501)},{action:'cancel',path:'../x'}]){
  assert.throws(()=>parseAudioCommand(value));
 }
});
test('WAV validation accepts only bounded canonical mono PCM16 at 16kHz',()=>{
 validateWav(wav());
 for(const [offset,value] of [[20,3],[22,2],[24,48000],[28,48000],[34,8],[40,200]]){
  const b=wav();b.writeUInt16LE(value,offset);assert.throws(()=>validateWav(b));
 }
 assert.throws(()=>validateWav(new Uint8Array(MAX_WAV_BYTES+1)));
 assert.throws(()=>validateWav(new Uint8Array(8)));
});
test('bounded streaming rejects declared and chunked oversized bodies and cancels stream',async()=>{
 await assert.rejects(readBounded(new Request('http://localhost',{method:'POST',headers:{'Content-Length':'10'},body:'x'}),4),/too large/);
 let cancelled=false;
 const stream=new ReadableStream<Uint8Array>({pull(controller){controller.enqueue(new Uint8Array(3));},cancel(){cancelled=true;}});
 const req=new Request('http://localhost',{method:'POST',body:stream,duplex:'half'} as RequestInit);
 await assert.rejects(readBounded(req,4),/too large/);assert.equal(cancelled,true);
 assert.equal((await readBounded(new Request('http://localhost',{method:'POST',body:'1234'}),4)).length,4);
});
test('audio route enforces origin, camera session, single pending controls and upload gates',async()=>{
 const dir=join(process.cwd(),`.audio-${randomUUID().slice(0,8)}`);
 process.env.DJOKER_DATA_DIR=dir;
 const route=await import('../app/api/live/audio/route');
 const request=(body:unknown,headers:Record<string,string>={})=>new Request('http://localhost/api/live/audio',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});
 const live=join(dir,'live');
 const received:{session_id:string;length:number;wav:Buffer}[]=[];
 let acknowledgment='{"accepted":true}\n';
 const server=createServer(socket=>{
  let data=Buffer.alloc(0),done=false;
  socket.on('data',chunk=>{
   data=Buffer.concat([data,chunk]);
   const newline=data.indexOf(10);if(done||newline<0)return;
   const header=JSON.parse(data.subarray(0,newline).toString('utf8'));
   if(data.length-newline-1<header.length)return;
   done=true;received.push({...header,wav:data.subarray(newline+1)});socket.end(acknowledgment);
  });
 });
 try{
  assert.equal((await route.POST(request({action:'cancel'},{origin:'https://foreign.example'}))).status,403);
  assert.equal((await route.POST(request({action:'enable',value:'yes'}))).status,400);
  assert.equal((await route.POST(request({action:'cancel'}))).status,409);
  await mkdir(live,{recursive:true});await writeFile(join(live,'status.json'),JSON.stringify(camera));
  await new Promise<void>((resolve,reject)=>{server.once('error',reject);server.listen(join(live,'audio.sock'),resolve);});
  const update=async(changes={})=>writeFile(join(live,'audio-status.json'),JSON.stringify({...audio,updated:Date.now()/1000,...changes}));
  await update();
  assert.equal((await (await route.GET()).json()).available,true);
  assert.equal((await route.POST(request({action:'mute',value:true},{host:'127.0.0.1:3017',origin:'http://127.0.0.1:3017'}))).status,202);
  assert.equal(JSON.parse(await readFile(join(live,'audio-command.json'),'utf8')).session_id,camera.session);
  assert.equal((await route.POST(request({action:'cancel'}))).status,409);
  await rm(join(live,'audio-command.json'));
  const upload=()=>route.POST(new Request('http://localhost/api/live/audio',{method:'POST',headers:{'Content-Type':'audio/wav'},body:wav()}));
  await update({state:'SPEAKING'});assert.equal((await upload()).status,409);
  await update({muted:true});assert.equal((await upload()).status,409);
  await update();assert.equal((await upload()).status,202);
  assert.deepEqual(received[0],{session_id:camera.session,length:wav().length,wav:wav()});
  await assert.rejects(readFile(join(live,'utterance.wav')),/ENOENT/);
  acknowledgment='{"error":"Audio session ended. Try again."}\n';assert.equal((await upload()).status,400);
  acknowledgment='x'.repeat(1025);assert.equal((await upload()).status,400);
  await update({listening:false});assert.equal((await upload()).status,409);
  assert.equal((await route.POST(new Request('http://localhost/api/live/audio',{method:'POST',headers:{'Content-Type':'audio/wav'},body:new Uint8Array(MAX_WAV_BYTES+1)}))).status,413);
  await update({updated:Date.now()/1000-6});assert.equal((await (await route.GET()).json()).enabled,false);
 }finally{if(server.listening)await new Promise<void>(resolve=>server.close(()=>resolve()));await rm(dir,{recursive:true,force:true});}
});
