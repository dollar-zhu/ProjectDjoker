import test from 'node:test';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {compareMotion,referencePhaseAt,referencePoseAt} from './motion-similarity';
import {projectPose} from './reference';
import {alignedReference} from './overlay';
const joints=[[5,11],[6,14],[7,12],[8,15],[9,13],[10,16],[11,4],[12,1],[13,5],[14,2],[15,6],[16,3]];
const reference=Array.from({length:101},(_,i)=>{
 const p=Array.from({length:17},()=>[0,0,0]);
 p[4]=[-.25,0,0];p[1]=[.25,0,0];p[11]=[-.4,0,1];p[14]=[.4,0,1];
 p[5]=[-.35,0,-.55];p[2]=[.35,0,-.55];p[6]=[-.45,0,-1.1];p[3]=[.45,0,-1.1];
 const rise=i<=80?Math.sin(i/80*Math.PI/2):Math.cos((i-80)/20*Math.PI/2);
 p[13]=[-.5-.25*Math.sin(i/100*Math.PI),0,.3+1.2*rise];p[16]=[.5+.3*Math.sin(i/100*Math.PI),0,.3+1.7*rise];
 p[12]=[-.6,0,.5+.5*rise];p[15]=[.65,0,.6+.7*rise];return p;
});
function fixture(warp=false){
 const frames=reference.map((p,i)=>{
  const xy=Array.from({length:17},()=>[0,0]);for(const[c,h]of joints){const q=projectPose(p,0)[h];xy[c]=[q[0]*100+500,q[1]*100+300];}
  const a=i<=40?0:i<=80?40:80,b=i<=40?40:i<=80?80:100;
  const t=(a+(b-a)*(warp?Math.pow((i-a)/(b-a),1.45):(i-a)/(b-a)))/20;
  return {time:t,xy,scores:Array(17).fill(.95)};
 });
 return {frames,reference,events:[{id:'loading',time:2},{id:'reach',time:4}],duration:5,view:'rear',handedness:'right',stages:[{id:'setup',status:'estimated',time:0,start:0,end:0},{id:'finish',status:'estimated',time:5,start:4.9,end:5}]};
}
test('identical projected motion scores 100 and supplies exact phase anchors',()=>{
 const r=compareMotion(fixture());assert.equal(r.status,'available');if(r.status!=='available')return;
 assert.equal(r.score,100);assert.equal(r.quality,'full');assert.ok(r.coverage<=1&&r.coverage>=0);assert.ok(Object.values(r.regionCoverage).every(v=>v<=1&&v>=0));assert.equal(referencePhaseAt(r.alignment,2),40);assert.equal(referencePhaseAt(r.alignment,4),80);
 assert.equal(referencePhaseAt(r.alignment,-.1),null);assert.equal(referencePhaseAt(r.alignment,5.1),null);
 assert.deepEqual(r.regionScores,{hittingArm:100,tossingArm:100,legs:100,torso:100});assert.deepEqual(r.phaseScores.map(p=>[p.phase,p.start,p.end,p.score]),[['preparation',0,2,100],['upward swing',2,4,100],['follow-through',4,5,100]]);
 assert.ok(r.alignment.every((p,i)=>i===0||p.referencePhase>=r.alignment[i-1].referencePhase));
});
test('alignment follows changing pace and keeps similar movement highly similar',()=>{
 const r=compareMotion(fixture(true));assert.equal(r.status,'available');if(r.status!=='available')return;
 assert.ok(r.score>=95,`score ${r.score}`);assert.ok(referencePhaseAt(r.alignment,1)!>23);
});
test('translation and fixed body scale do not change similarity',()=>{
 const f=fixture();f.frames=f.frames.map(x=>({...x,xy:x.xy.map(([a,b])=>[a*1.6+300,b*1.6-100])}));
 const r=compareMotion(f);assert.equal(r.status,'available');if(r.status==='available')assert.equal(r.score,100);
});
test('meaningful limb deviations reduce score rather than being warped away',()=>{
 const f=fixture();for(const p of f.frames){p.xy[10][0]+=80;p.xy[8][0]+=50;}
 const r=compareMotion(f);assert.equal(r.status,'available');if(r.status!=='available')return;assert.ok(r.score<85);
 const regions=r.regionScores as Record<string,number>;assert.equal(Object.entries(regions).sort((a,b)=>a[1]-b[1])[0][0],'hittingArm');assert.equal(regions.legs,100);
});
test('missing whole phase and incomplete tail are not full-motion scores',()=>{
 const f=fixture();f.frames=f.frames.filter(p=>p.time<2.3||p.time>3.6);assert.equal(compareMotion(f).status,'unavailable');
 const tail=fixture();tail.frames=tail.frames.filter(p=>p.time<4.3);tail.duration=4.3;tail.stages=[];
 const r=compareMotion(tail);assert.equal(r.status,'unavailable');if(r.status==='unavailable')assert.match(r.reason,/follow-through|complete|finish/i);
});
test('an unobserved hitting arm, incompatible views and corrupt references withhold a number',()=>{
 const f=fixture();for(const p of f.frames){p.scores[8]=.1;p.scores[10]=.1;}assert.equal(compareMotion(f).status,'unavailable');
 assert.equal(compareMotion({...fixture(),view:'side'}).status,'unavailable');assert.equal(compareMotion({...fixture(),handedness:'left'}).status,'unavailable');
 assert.equal(compareMotion({...fixture(),reference:[]}).status,'unavailable');
 const bad=fixture();bad.reference=structuredClone(reference);bad.reference[10][5][0]=NaN;assert.equal(compareMotion(bad).status,'unavailable');
});
test('invalid timestamps and phase events do not create a plausible score',()=>{
 const f=fixture();f.frames[10].time=f.frames[9].time;assert.equal(compareMotion(f).status,'unavailable');assert.equal(compareMotion({...fixture(),events:[]}).status,'unavailable');
});
test('incomplete follow-through still offers an explicitly partial setup-to-reach replay',()=>{
 const f=fixture();f.stages=f.stages.filter(s=>s.id==='setup');f.frames=f.frames.filter(p=>p.time<=4.2);f.duration=4.2;
 const r=compareMotion(f);assert.equal(r.status,'unavailable');if(r.status!=='unavailable')return;
 assert.ok(r.alignment?.length);assert.ok(r.fit);assert.equal(referencePhaseAt(r.alignment!,4),80);assert.equal(referencePhaseAt(r.alignment!,4.1),null);
});
test('a brief uncertain elbow does not erase an otherwise observed serve',()=>{
 const f=fixture();f.frames[55].scores[8]=.2;
 const r=compareMotion(f);assert.equal(r.status,'available');if(r.status==='available')assert.ok(r.score>=99);
});
test('a prolonged hidden arm yields preview only, never a leg-dominated score',()=>{
 const f=fixture();for(const p of f.frames)if(p.time>4.1){p.scores[8]=.2;p.scores[10]=.2;}
 const r=compareMotion(f);assert.equal(r.status,'unavailable');if(r.status==='unavailable'){assert.ok(r.alignment);assert.ok(!('score' in r));}
});
test('walk-in and walk-out never stretch the movement or appear in mapping',()=>{
 const f=fixture();f.frames=f.frames.map(p=>({...p,time:p.time+10}));f.duration=25;
 f.events=f.events.map(e=>({...e,time:e.time+10}));f.stages=f.stages.map(s=>({...s,time:s.time+10,start:s.start+10,end:s.end+10}));
 const r=compareMotion(f);assert.equal(r.status,'available');if(r.status==='available'){assert.equal(r.score,100);assert.equal(referencePhaseAt(r.alignment,9),null);assert.equal(referencePhaseAt(r.alignment,16),null);}
});

test('fractional reference phases interpolate joints and refuse out-of-range samples',()=>{
 const pose=referencePoseAt(reference,40.5);assert.ok(pose);
 assert.deepEqual(pose,reference[40].map((p,j)=>p.map((v,k)=>(v+reference[41][j][k])/2)));
 assert.deepEqual(referencePoseAt(reference,100),reference[100]);
 assert.equal(referencePoseAt(reference,-.1),null);assert.equal(referencePoseAt(reference,100.1),null);assert.equal(referencePoseAt(reference,NaN),null);
});
test('score uses distances to exactly the interpolated pose rendered by the overlay',()=>{
 const f=fixture(true),r=compareMotion(f);assert.equal(r.status,'available');if(r.status!=='available')return;
 assert.ok(r.alignment.some(p=>p.referencePhase%1!==0));
 let error=0;
 for(const [start,end,weight]of [[0,2,.4],[2,4,.4],[4,5,.2]]){
  const samples=r.alignment.filter(p=>p.time>=start&&p.time<=end);let phaseError=0;
  for(const sample of samples){
   const index=f.frames.findIndex(p=>p.time>=sample.time-1e-8),b=f.frames[index],a=f.frames[Math.max(0,index-1)];
   const mix=b.time===a.time?0:(sample.time-a.time)/(b.time-a.time);
   const frame={...b,time:sample.time,xy:a.xy.map((p,j)=>p.map((v,k)=>v+(b.xy[j][k]-v)*mix))};
   const ghost=alignedReference(referencePoseAt(reference,sample.referencePhase)!,frame,r.fit)!;
   for(const[keys,regionWeight]of [[[3,5],.35],[[2,4],.25],[[8,9,10,11],.3],[[0,1,6,7],.1]] as [number[],number][]){
    phaseError+=regionWeight*Math.sqrt(keys.reduce((sum,k)=>{const[c,h]=joints[k];return sum+(frame.xy[c][0]-ghost[h][0])**2+(frame.xy[c][1]-ghost[h][1])**2;},0)/keys.length)/100;
   }
  }
  error+=weight*phaseError/samples.length;
 }
 assert.ok(Math.abs(r.meanDistance-error)<1e-10,`distance ${r.meanDistance} versus rendered ${error}`);
});

test('hidden hitting wrist after peak retains a partial score from observed arm and body',()=>{
 const f=fixture();for(const p of f.frames)if(p.time>4)p.scores[10]=.2;
 const r=compareMotion(f);assert.equal(r.status,'available');if(r.status!=='available')return;
 assert.equal(r.quality,'partial');assert.equal(r.alignment.at(-1)!.referencePhase,100);assert.ok(r.score>=99);
 assert.ok(r.excludedMeasurements.some(s=>/hitting wrist.*follow-through/i.test(s)));assert.ok(r.regionCoverage.hittingArm<1);
});
test('observed elbow descent plus body recovery completes despite wrist loss',()=>{
 const f=fixture();f.stages=f.stages.filter(s=>s.id==='setup');
 for(const p of f.frames)if(p.time>4){p.scores[10]=.2;if(p.time>4.3)p.xy=p.xy.map(([x,y])=>[x,y+12]);}
 const last=f.frames.at(-1)!;for(let i=1;i<=6;i++)f.frames.push({...last,time:5+i*.05});f.duration=5.3;
 const r=compareMotion(f);assert.equal(r.status,'available');if(r.status==='available'){assert.equal(r.quality,'partial');assert.equal(r.alignment.at(-1)!.referencePhase,100);}
});
test('latest saved serve aligns through observed recovery and returns an explicitly partial score',()=>{
 const f=JSON.parse(readFileSync(new URL('./fixtures/serve-similarity-f90.json',import.meta.url),'utf8'));
 const r=compareMotion({...f,reference,view:'rear',handedness:'right'});assert.equal(r.status,'available',r.status==='unavailable'?r.reason:'');if(r.status!=='available')return;
 assert.equal(r.quality,'partial');assert.ok(Number.isFinite(r.score));assert.equal(r.alignment.at(-1)!.referencePhase,100);assert.equal(r.alignment.at(-1)!.time,4.25);assert.ok(r.excludedMeasurements.some(s=>/hitting wrist/i.test(s)));
});

test('cached fallback and refreshed stage metadata produce the same recovery endpoint',()=>{
 const f=JSON.parse(readFileSync(new URL('./fixtures/serve-similarity-f90.json',import.meta.url),'utf8'));
 const cached=compareMotion({...f,reference,view:'rear',handedness:'right'});
 f.stages=f.stages.filter((s:{id:string})=>s.id!=='finish');f.stages.push({id:'finish',status:'estimated',time:4.25,start:3.85,end:4.25});
 const refreshed=compareMotion({...f,reference,view:'rear',handedness:'right'});
 assert.equal(cached.status,'available');assert.equal(refreshed.status,'available');
 if(cached.status==='available'&&refreshed.status==='available'){assert.deepEqual(cached.alignment,refreshed.alignment);assert.equal(cached.score,refreshed.score);}
});
test('two observed reach frames at 20fps still align a fast serve through recovery',()=>{
 const f=fixture();f.stages=f.stages.filter(s=>s.id==='setup');
 for(const p of f.frames)p.xy[10][1]=p.time>=3.95&&p.time<=4?p.xy[6][1]-75:p.xy[6][1]+50;
 const r=compareMotion(f);assert.equal(r.status,'available',r.status==='unavailable'?r.reason:'');
 if(r.status==='available'){assert.equal(r.alignment.at(-1)!.referencePhase,100);assert.equal(r.alignment.at(-1)!.time,4.35);}
});

test('11:21:34 recording keeps the upward swing and finish through a brief shoulder-confidence dip',()=>{
 const f=JSON.parse(readFileSync(new URL('./fixtures/serve-similarity-026.json',import.meta.url),'utf8'));
 const before=structuredClone(f);
 const r=compareMotion({...f,reference,view:'rear',handedness:'right'});
 assert.equal(r.status,'available',r.status==='unavailable'?r.reason:'');if(r.status!=='available')return;
 assert.equal(r.quality,'partial');assert.equal(r.alignment[0].time,1.35);
 assert.equal(r.alignment.at(-1)!.time,3.55);assert.equal(r.alignment.at(-1)!.referencePhase,100);
 assert.equal(referencePhaseAt(r.alignment,3.05),80);
 assert.ok(referencePhaseAt(r.alignment,2.85)!>40);
 assert.ok(r.excludedMeasurements.some(s=>/shoulder.*upward swing/i.test(s)));
 assert.ok(r.regionCoverage.hittingArm<1);assert.deepEqual(f,before);
});

test('brief upper-body confidence loss keeps alignment without counting uncertain joints',()=>{
 const f=fixture();
 for(const p of f.frames)if(p.time>=2.8&&p.time<=2.85)for(const j of [5,6,7,8,9,10]){p.scores[j]=.2;p.xy[j]=[10000,-10000];}
 const r=compareMotion(f);assert.equal(r.status,'available',r.status==='unavailable'?r.reason:'');if(r.status!=='available')return;
 assert.equal(r.quality,'partial');assert.ok(r.score>=99);assert.ok(r.regionCoverage.torso<1);
 assert.equal(r.alignment.at(-1)!.time,5);assert.ok(r.alignment.every((p,i)=>i===0||p.referencePhase>=r.alignment[i-1].referencePhase));
});

test('sustained torso loss or missing hip anchors still prevents a whole-motion score',()=>{
 for(const hips of [false,true]){
  const f=fixture();
  for(const p of f.frames)if(p.time>=2.8&&p.time<=(hips?2.85:3.2))for(const j of hips?[11,12]:[5,6])p.scores[j]=.2;
  const r=compareMotion(f);assert.equal(r.status,'unavailable');assert.ok(!('score' in r));
 }
});

test('12:26:24 live recording retains recovery from original camera observations',()=>{
 const f=JSON.parse(readFileSync(new URL('../../processor/fixtures/live-serve-168.json',import.meta.url),'utf8'));
 const r=compareMotion({frames:f.frames,reference,events:[{id:'loading',time:1.8096},{id:'reach',time:2.3389}],duration:f.meta.duration,view:'rear',handedness:'right',stages:[{id:'setup',status:'estimated',time:.8317,start:.6,end:.8317}]});
 assert.equal(r.status,'available',r.status==='unavailable'?r.reason:'');if(r.status!=='available')return;
 assert.equal(r.quality,'partial');assert.equal(r.alignment.at(-1)!.time,2.8069);
 assert.equal(r.alignment.at(-1)!.referencePhase,100);
 assert.ok(r.excludedMeasurements.some(s=>/hitting wrist.*follow-through/i.test(s)));
});

test('an invalid setup anchor reports setup uncertainty without blaming the observed finish',()=>{
 const f=fixture();f.stages[0]={id:'setup',status:'estimated',time:1.95,start:1.7,end:1.95};
 const r=compareMotion(f);assert.equal(r.status,'unavailable');if(r.status!=='unavailable')return;
 assert.match(r.reason,/setup/i);assert.doesNotMatch(r.reason,/follow-through|finish|record the whole serve/i);
});

test('12:32:47 recording scores with the observed pre-raise setup despite an occluded toss',()=>{
 const f=JSON.parse(readFileSync(new URL('../../processor/fixtures/serve-setup-2b7.json',import.meta.url),'utf8'));
 // This endpoint is independently recovered from these joints by test_stages.py.
 f.stages=f.stages.map((s:{id:string})=>s.id==='setup'?{...s,time:1.8083,start:1.5913,end:1.8083}:s);
 const r=compareMotion({...f,reference,view:'rear',handedness:'right'});
 assert.equal(r.status,'available',r.status==='unavailable'?r.reason:'');if(r.status!=='available')return;
 assert.equal(r.alignment[0].time,1.8083);assert.equal(r.alignment.at(-1)!.time,3.8153);
 assert.equal(r.quality,'partial');assert.ok(r.excludedMeasurements.some(s=>/tossing wrist/i.test(s)));
});
