import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import * as review from '../components/movement-review';

test('coaching shows a cue, drill, success check and linked video evidence',()=>{
 assert.equal(typeof review.CoachFeedback,'function','Feedback needs its own drill and success-check presentation');
 const html=renderToStaticMarkup(createElement(review.CoachFeedback,{analysis:{focus_id:'rhythm',title:'Keep the rhythm',observation:'The knees bend and rise.',rationale:'Practise this sequence.',cue:'Bend and rise.',drill:'Film five shadow serves.',success_check:'Compare the rise across repetitions.',limitation:'Contact is not established.',note:'Contact is not established.',source:'Gemma 4 E2B · Ventuno CPU · reviewed practice content',model_status:'completed',evidence_times:[2.35]},onSeek:()=>{}}));
 for(const text of ['Try this','What to check','Film five','2.35s','Gemma 4 E2B']) assert.ok(html.includes(text));
 assert.ok(html.includes('Ventuno'));
});

test('unavailable model is clearly a reviewed fallback, not generated coaching',()=>{
 assert.equal(typeof review.CoachFeedback,'function');
 const html=renderToStaticMarkup(createElement(review.CoachFeedback,{analysis:{focus_id:'recapture',title:'Record again',observation:'Tracking is incomplete.',rationale:'Get a complete recording.',cue:'Include the feet.',drill:'Record one full motion.',success_check:'Feet remain visible.',limitation:'No contact evidence.',note:'No contact evidence.',source:'Reviewed practice card · fallback',model_status:'unavailable',evidence_times:[]},onSeek:()=>{}}));
 assert.ok(html.includes('unavailable'));assert.ok(html.includes('fallback'));assert.ok(!html.includes('Evidence frames'));
});

 test('coaching describes its board and evidence role accurately',()=>{
 const html=renderToStaticMarkup(createElement(review.MovementInsight,{jobId:'example',stages:[],active:'',onReplay:()=>{},onSelect:()=>{}}));
 assert.ok(html.includes('Ventuno'));assert.ok(!html.includes('sampled video frames'));
 });

test('insufficient evidence asks for a usable recording without claiming the model failed',()=>{
 const html=renderToStaticMarkup(createElement(review.CoachFeedback,{analysis:{focus_id:'recapture',title:'Get a clearer view',observation:'Frames repeat.',rationale:'An uninterrupted recording is needed.',cue:'Record the movement.',drill:'Use the original video.',success_check:'Whole movement is visible.',limitation:'No timing evidence.',source:'Recording review · more evidence needed',model_status:'insufficient_evidence',evidence_times:[]}}));
 assert.ok(!html.includes('Gemma 4 is unavailable'));assert.ok(!html.includes('try again'));
});

test('an evidence jump keeps the coaching stage selected after seeking',()=>{
 let active='acceleration',time=0;
 const tree=review.CoachFeedback({analysis:{focus_id:'rhythm',stage_id:'acceleration',title:'Rhythm',observation:'Knees bend then rise.',rationale:'Compare the sequence.',cue:'Bend and rise.',drill:'Film five repetitions.',success_check:'Compare the rise.',limitation:'Contact unknown.',source:'Gemma 4 E2B · Ventuno CPU',model_status:'completed',evidence_times:[3.55]},onSeek:t=>{time=t;active='';},onSelect:id=>{active=id;}});
 function findButton(node:any):any {if(!node||typeof node!=='object')return null;if(node.type==='button')return node;const children=Array.isArray(node.props?.children)?node.props.children:[node.props?.children];for(const child of children.flat()){const found=findButton(child);if(found)return found;}return null;}
 findButton(tree).props.onClick();assert.equal(time,3.55);assert.equal(active,'acceleration');
});
