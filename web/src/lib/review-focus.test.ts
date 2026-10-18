import test from 'node:test';
import assert from 'node:assert/strict';
import {bodyFocus,formatMeasurement,reviewWindow,stageLanes} from './review-focus';

const stage=(id:string,start:number|null,end:number|null)=>({id,start,end,status:start===null?'unavailable' as const:'estimated' as const});
test('stage focus names the body part and mirrors joints for left-handed players',()=>{
 assert.equal(bodyFocus('loading')?.part,'Knees');assert.deepEqual(bodyFocus('toss')?.joints,[5,7,9]);
 assert.deepEqual(bodyFocus('toss','left')?.joints,[6,8,10]);assert.equal(bodyFocus('unknown'),null);assert.equal(bodyFocus(null),null);
});
test('measurements get readable labels and units',()=>{
 assert.deepEqual(formatMeasurement('left_knee_deg',151.8),{label:'Left knee',value:'152°'});
 assert.deepEqual(formatMeasurement('mean_knee_change_deg',30.4),{label:'Knee extension',value:'+30°'});
 assert.equal(formatMeasurement('wrist_rise_torso_lengths',.891).value,'0.89×');
 assert.equal(formatMeasurement('some_new_metric',1.234).label,'Some new metric');
 assert.equal(formatMeasurement('left_knee_deg',NaN).value,'—');
});
test('review window pads estimated stages and falls back to the full clip',()=>{
 assert.deepEqual(reviewWindow([stage('setup',1.5,1.75),stage('finish',3.85,4.25),stage('toss',null,null)],5.2),[1.15,4.6]);
 assert.deepEqual(reviewWindow([stage('setup',.1,1)],1.2),[0,1.2]);
 assert.deepEqual(reviewWindow([],5),[0,5]);
});
test('overlapping stages are packed into separate lanes',()=>{
 const lanes=stageLanes([stage('setup',1.5,1.75),stage('toss',2.05,2.8),stage('loading',2.6,2.9),stage('acceleration',2.8,3.55),stage('missing',null,null)]);
 assert.deepEqual(lanes.map(l=>[l.stage.id,l.lane]),[['setup',0],['toss',0],['loading',1],['acceleration',0]]);
});
