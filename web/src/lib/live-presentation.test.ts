import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

test('continuous capture is the default and needs no ready gesture',async()=>{
 const {LiveCapture}=await import('../components/live-capture');
 const html=renderToStaticMarkup(createElement(LiveCapture,{onReview:()=>{}}));
 assert.match(html,/value="continuous" selected=""/);
 assert.match(html,/value="auto">Ready gesture/,'The ready gesture remains available');
 assert.match(html,/Stand still in frame/);
 assert.doesNotMatch(html,/3-second countdown/);
});

test('continuous cue shows settling, watching and detection, never a countdown',async()=>{
 const {CaptureCue}=await import('../components/live-capture');
 const cue=(state:string,readyProgress=0)=>renderToStaticMarkup(createElement(CaptureCue,{live:{active:true,state,countdown:null,elapsed:0,readyProgress,mode:'continuous'}}));
 assert.match(cue('waiting',.5),/Getting set/);
 assert.equal(cue('waiting'),'');
 assert.match(cue('watching'),/Watching/);
 assert.match(cue('recording'),/Serve detected/);
 assert.doesNotMatch(cue('recording'),/GO/);
 const after=(event:string,updated:number,state='cooldown')=>renderToStaticMarkup(createElement(CaptureCue,{live:{active:true,state,countdown:null,readyProgress:0,mode:'continuous',updated,lastEvent:{event,number:2,at:100}}}));
 assert.match(after('complete',101),/Serve 2 captured/);
 assert.match(after('complete',102,'waiting'),/Serve 2 captured/,'Confirmation outlasts the cooldown');
 assert.doesNotMatch(after('complete',104,'waiting'),/captured/);
 assert.match(after('discard',101),/still watching/);
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
