import test from 'node:test';
import assert from 'node:assert/strict';
import {POST} from '../app/api/commentary/route';
test('commentary rejects foreign origins and unsupported measurements before invoking the board',async()=>{
 const req=(body:unknown,origin?:string)=>new Request('http://localhost/api/commentary',{method:'POST',headers:{'Content-Type':'application/json',...(origin?{origin}:{})},body:JSON.stringify(body)});
 assert.equal((await POST(req({},'https://foreign.example'))).status,403);
 assert.equal((await POST(req({player:'Novak Djokovic',time:1,userLeft:200}))).status,400);
});
test('same-origin host header works when Next normalizes its internal request URL',async()=>{
 const r=await POST(new Request('http://localhost:3017/api/commentary',{method:'POST',headers:{host:'127.0.0.1:3017',origin:'http://127.0.0.1:3017','Content-Type':'application/json'},body:'{}'}));
 assert.equal(r.status,400);
});
test('stage analysis reads a stored job and never accepts client-supplied stage evidence',async()=>{
 const req=(body:unknown)=>new Request('http://localhost/api/commentary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 assert.equal((await POST(req({jobId:'../private'}))).status,400);
 assert.equal((await POST(req({jobId:'00000000-0000-0000-0000-000000000000'}))).status,404);
 assert.equal((await POST(req({jobId:'00000000-0000-0000-0000-000000000000',stages:[{id:'contact'}]}))).status,400);
});
