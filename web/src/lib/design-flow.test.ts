import test from 'node:test';
import assert from 'node:assert/strict';
import {designHref,parseConcept} from './design-flow';

test('recording and review links preserve each selected design',()=>{
 for(const concept of ['courtside','coach','studio'] as const){
  assert.equal(designHref(concept,true),`/designs/serve?concept=${concept}`);
  assert.equal(designHref(concept,false),`/designs?concept=${concept}`);
 }
});
test('unknown design links fall back to the recording-first concept',()=>{
 assert.equal(parseConcept(undefined),'courtside');
 assert.equal(parseConcept('unknown'),'courtside');
 assert.equal(parseConcept('coach'),'coach');
});
