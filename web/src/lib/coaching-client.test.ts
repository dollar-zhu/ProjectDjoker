import test from 'node:test';
import assert from 'node:assert/strict';
import * as coaching from './coaching-client';

test('automatic coaching shares an in-flight request and allows a later retry',async()=>{
 let calls=0,finish!:(response:Response)=>void;
 const fetcher=(async (_url:unknown,init:RequestInit)=>{
  calls++;assert.deepEqual(JSON.parse(init.body as string),{jobId:'serve-a'});
  return await new Promise<Response>(resolve=>{finish=resolve;});
 }) as typeof fetch;
 const a=coaching.loadCoaching('serve-a',fetcher),b=coaching.loadCoaching('serve-a',fetcher);
 assert.equal(calls,1);
 const plan={title:'Measured plan',model_status:'completed'};
 finish(Response.json(plan));assert.deepEqual(await a,plan);assert.deepEqual(await b,plan);
 const retry=coaching.loadCoaching('serve-a',fetcher);assert.equal(calls,2);
 finish(Response.json(plan));await retry;
});

test('a failed request reports the error and allows retry without invented feedback',async()=>{
 await assert.rejects(coaching.loadCoaching('serve-b',(async()=>Response.json({error:'Offline'},{status:503})) as typeof fetch),/Offline/);
 const plan={model_status:'completed',title:'Fresh analysis'};
 assert.deepEqual(await coaching.loadCoaching('serve-b',(async()=>Response.json(plan)) as typeof fetch),plan);
});

test('server feedback and insufficient evidence are preserved exactly',async()=>{
 for(const model_status of ['insufficient_evidence','unavailable','busy','reply_rejected']){
  const plan={model_status,observation:'Current analysis unavailable.',evidence_times:[],source:'Recording review'};
  assert.deepEqual(await coaching.loadCoaching(model_status,(async()=>Response.json(plan)) as typeof fetch),plan);
 }
});
