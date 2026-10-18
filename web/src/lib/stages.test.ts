import test from 'node:test';
import assert from 'node:assert/strict';
import * as playback from './playback';

test('stage replay uses its interval and refuses unavailable or invalid stages',()=>{
 assert.equal(typeof playback.stagePlayback,'function');
 assert.deepEqual(playback.stagePlayback({status:'estimated',start:1,end:2,time:1.5},3),{start:1,end:2,rate:.25});
 assert.equal(playback.stagePlayback({status:'unavailable',start:null,end:null,time:null},3),null);
 assert.equal(playback.stagePlayback({status:'estimated',start:2,end:1,time:1.5},3),null);
 assert.equal(playback.stagePlayback({status:'estimated',start:1,end:4,time:2},3),null);
});
