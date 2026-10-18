import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

test('automatic capture presents a deliberate ready gesture by default',async()=>{
 const {LiveCapture}=await import('../components/live-capture');
 const html=renderToStaticMarkup(createElement(LiveCapture,{onReview:()=>{}}));
 assert.match(html,/value="auto" selected=""/);
 assert.match(html,/shoulder height/);
 assert.match(html,/3-second countdown/);
});

test('camera cue renders backend countdown and recording separately',async()=>{
 const component=await import('../components/live-capture');
 assert.equal(typeof component.CaptureCue,'function','CaptureCue must render authoritative capture state');
 const cue=(state:string,countdown:number|null,elapsed=0)=>renderToStaticMarkup(createElement(component.CaptureCue,{live:{active:true,state,countdown,elapsed,readyProgress:0,mode:'auto'}}));
 assert.match(cue('countdown',3),/aria-label="Serve starts in 3"/);
 assert.match(cue('countdown',1),/>1</);
 assert.doesNotMatch(cue('waiting',3),/Serve starts/,'A cancelled countdown must disappear');
 assert.match(cue('recording',null),/GO/);
 assert.doesNotMatch(cue('recording',null,2),/GO/);
});
