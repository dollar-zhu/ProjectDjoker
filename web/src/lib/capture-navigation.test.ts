import test from 'node:test';
import assert from 'node:assert/strict';
import {reviewFromCapture} from './capture-navigation';
test('opening the recorder ignores a retained completed serve',()=>{
 assert.equal(reviewFromCapture(null,{state:'waiting',jobId:'old'}),null);
 assert.equal(reviewFromCapture({state:'waiting',jobId:'old'},{state:'recording',jobId:'old'}),null);
});
test('a newly saved capture opens its own review while processing',()=>{
 assert.equal(reviewFromCapture({state:'processing',jobId:'old'},{state:'processing',jobId:'new'}),'new');
 assert.equal(reviewFromCapture({state:'processing'},{state:'processing',jobId:'new'}),'new');
});
test('rejoining an in-flight capture opens it when processing finishes',()=>{
 assert.equal(reviewFromCapture({state:'processing',jobId:'new'},{state:'waiting',jobId:'new'}),'new');
 assert.equal(reviewFromCapture({state:'waiting',jobId:'new'},{state:'waiting',jobId:'new'}),null);
});
