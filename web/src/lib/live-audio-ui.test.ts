import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LiveAudio} from '../components/live-audio';

test('voice controls explain the next step and keep setup details collapsed',()=>{
 const html=renderToStaticMarkup(createElement(LiveAudio,{active:false}));
 assert.match(html,/Start the camera to connect voice/);
 assert.match(html,/<details[^>]*><summary>Voice setup &amp; diagnostics<\/summary>/);
 assert.doesNotMatch(html,/<details[^>]*open/);
 assert.doesNotMatch(html,/not the adb board/);
 for(const label of ['Enable voice','Unmute','Cancel speech','Hold to talk','Ask the coach','Send question'])assert.ok(html.includes(label));
 const buttons=html.match(/<button[^>]*>/g)||[];
 assert.equal(buttons.length,4);
 assert.ok(buttons.every(button=>button.includes('disabled')));
});
