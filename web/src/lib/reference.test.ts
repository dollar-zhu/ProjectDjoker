import test from 'node:test';
import assert from 'node:assert/strict';
import {phaseAt,projectPose,kneeAngle} from './reference';
test('phase alignment preserves load and reach anchors and clamps the ends',()=>{
 const events=[{id:'loading',time:1},{id:'reach',time:2}];
 assert.equal(phaseAt(1,3,events),40);assert.equal(phaseAt(2,3,events),80);
 assert.equal(phaseAt(1.5,3,events),60);assert.equal(phaseAt(9,3,events),100);assert.equal(phaseAt(-1,3,events),0);
});
test('missing or unordered events never imply synchronization',()=>{
 assert.equal(phaseAt(1,3,[]),null);assert.equal(phaseAt(1,3,[{id:'loading',time:2},{id:'reach',time:1}]),null);
});
test('projection preserves vertical direction; angles reject degenerate joints',()=>{
 assert.deepEqual(projectPose([[1,2,3]],0),[[1,-3]]);assert.equal(kneeAngle([0,0],[0,1],[0,2]),180);assert.equal(kneeAngle([0,0],[0,0],[0,2]),null);
});
