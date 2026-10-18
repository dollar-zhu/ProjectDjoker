import test from 'node:test';
import assert from 'node:assert/strict';
import {frameAt} from './playback';
test('overlay follows playback seeks and disappears beyond sampled evidence',()=>{
 const frames=[{time:0},{time:.05},{time:.1}];
 assert.equal(frameAt(frames,.04),frames[1]);
 assert.equal(frameAt(frames,0),frames[0]);
 assert.equal(frameAt(frames,.09),frames[2]);
 assert.equal(frameAt(frames,.4),null);
 assert.equal(frameAt([],0),null);
});
