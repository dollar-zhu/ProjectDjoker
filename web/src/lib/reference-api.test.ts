import test from 'node:test';
import assert from 'node:assert/strict';
import {GET} from '../app/api/references/route';
test('reference endpoint exposes selected poses and rejects path/subtype mismatches',async()=>{
 assert.equal((await GET(new Request('http://localhost/api/references?player=../private'))).status,400);
 const r=await GET(new Request('http://localhost/api/references?player=sinner&type=2'));
 assert.equal(r.status,200);const data=await r.json();assert.equal(data.poses.length,101);assert.ok(data.serves.length>0&&data.serves.length<67);assert.equal(data.view.view,'rear');assert.equal(data.view.sourceView,'unknown');
 const mismatch=await GET(new Request(`http://localhost/api/references?player=sinner&type=1&serve=${data.selected}`));
 assert.equal(mismatch.status,422);
});
