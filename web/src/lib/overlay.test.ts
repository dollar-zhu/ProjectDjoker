import test from 'node:test';
import assert from 'node:assert/strict';
import {fitReference,alignedReference,loadingEvidence} from './overlay';
import {projectPose} from './reference';
const ref=Array.from({length:17},(_,i)=>[i*.1,i*.2,i*.3]);
ref[4]=[-.4,0,0];ref[1]=[.4,0,0];ref[11]=[-.5,0,1];ref[14]=[.5,0,1];
const map=[[11,4],[12,1],[5,11],[6,14],[13,5],[14,2],[15,6],[16,3]];
function user(){const xy=Array.from({length:17},()=>[0,0]);const p=projectPose(ref,20);for(const[c,h]of map)xy[c]=[p[h][0]*100+500,p[h][1]*100+300];return{time:1,xy,scores:Array(17).fill(.9)};}
test('alignment uses torso anchors, preserves limb differences and follows pelvis',()=>{
 const u=user(),fit=fitReference(ref,u);assert.ok(fit);assert.ok(Math.abs(fit.scale-100)<1);
 const aligned=alignedReference(ref,u,fit);assert.ok(aligned);assert.ok(Math.abs((aligned[1][0]+aligned[4][0])/2-500)<1e-6);
 const moved={...u,xy:u.xy.map(([x,y])=>[x+30,y+40])};const shifted=alignedReference(ref,moved,fit)!;
 assert.ok(Math.abs(shifted[5][0]-aligned[5][0]-30)<1e-6);
});
test('missing anchors disable alignment and low-confidence knees withhold commentary',()=>{
 const u=user();u.scores[11]=.1;assert.equal(fitReference(ref,u),null);
 assert.equal(loadingEvidence(u,ref,'Novak Djokovic',1),null);
});
test('rear overlay stays fixed even when the user pose favors another angle',()=>{
 const u=user();const fit=fitReference(ref,u)!;
 assert.equal(fit.mirror,false);
 assert.equal(fit.yaw,0);
 const opposite={...u,xy:u.xy.map(([x,y])=>[1000-x,y])};
 assert.equal(fitReference(ref,opposite)!.mirror,false);
 assert.equal(fitReference(ref,opposite)!.yaw,0);
});
