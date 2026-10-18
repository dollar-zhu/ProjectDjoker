import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

test('similarity shows an experimental score and identifies the selected reference',async()=>{
 const component=await import('../components/reference-review');
 assert.equal(typeof component.SimilaritySummary,'function');
 const html=renderToStaticMarkup(createElement(component.SimilaritySummary,{player:'Novak Djokovic',comparison:{status:'available',score:78,coverage:.9}}));
 assert.match(html,/78/);assert.match(html,/100/);assert.match(html,/Novak Djokovic/);
 assert.match(html,/EXPERIMENTAL BODY SIMILARITY/);
 assert.match(html,/technique quality/);
});

test('missing movement evidence shows its reason instead of a zero score',async()=>{
 const component=await import('../components/reference-review');
 assert.equal(typeof component.SimilaritySummary,'function');
 const html=renderToStaticMarkup(createElement(component.SimilaritySummary,{player:'Novak Djokovic',comparison:{status:'unavailable',reason:'The hitting wrist is unclear during the finish.'}}));
 assert.match(html,/The hitting wrist is unclear during the finish/);
 assert.match(html,/Score unavailable/);
 assert.doesNotMatch(html,/\/ 100/);
});

test('an occluded wrist preserves the score and explains measurement coverage',async()=>{
 const {SimilaritySummary}=await import('../components/reference-review');
 const html=renderToStaticMarkup(createElement(SimilaritySummary,{player:'Novak Djokovic',comparison:{status:'available',score:72,coverage:.93,quality:'partial',excludedMeasurements:['Follow-through: hitting wrist partly hidden.'],regionCoverage:{hittingArm:.7,tossingArm:.95,legs:1,torso:1}}}));
 assert.match(html,/>72</);
 assert.match(html,/93%/);
 assert.match(html,/hitting wrist partly hidden/);
 assert.match(html,/Hitting arm/);
 assert.doesNotMatch(html,/Score unavailable/);
});

test('a low-confidence fallback score shows its number and the reason',async()=>{
 const {SimilaritySummary}=await import('../components/reference-review');
 const html=renderToStaticMarkup(createElement(SimilaritySummary,{player:'Novak Djokovic',comparison:{status:'available',score:41,coverage:.4,quality:'low',warnings:['A clear overhead reach is needed for a complete serve comparison.']}}));
 assert.match(html,/>41</);assert.match(html,/Low-confidence estimate/);assert.match(html,/clear overhead reach/);
});
