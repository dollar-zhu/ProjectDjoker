import {projectPose} from './reference';
import {fitReference,type Fit,type PoseFrame} from './overlay';

export type MotionAlignment = {time:number;referencePhase:number}[];
export type RegionCoverage = {hittingArm:number;tossingArm:number;legs:number;torso:number};
export type RegionScores = Record<keyof RegionCoverage,number|null>;
export type PhaseScore = {phase:string;start:number;end:number;score:number|null};
type Stage = {id:string;status:string;time:number|null;start:number|null;end:number|null};
export type MotionInput = {frames:PoseFrame[];reference:number[][][];events:{id:string;time:number}[];duration:number;view:string;handedness:string;stages?:Stage[]};
export type MotionSimilarity = {status:'unavailable';reason:string;alignment?:MotionAlignment;fit?:Fit;coverage?:number} | {status:'available';score:number;alignment:MotionAlignment;fit:Fit;meanDistance:number;coverage:number;quality:'full'|'partial'|'low';warnings:string[];excludedMeasurements:string[];regionCoverage:RegionCoverage;regionScores:RegionScores;phaseScores:PhaseScore[];method:string};
// COCO left/right correspondences are identical to the rear overlay. Strict scores use no yaw or mirror search.
const JOINTS=[[5,11],[6,14],[7,12],[8,15],[9,13],[10,16],[11,4],[12,1],[13,5],[14,2],[15,6],[16,3]];
const REGIONS=[
 {id:'hittingArm',label:'Hitting arm',joints:[3,5],weight:.35},
 {id:'tossingArm',label:'Tossing arm',joints:[2,4],weight:.25},
 {id:'legs',label:'Legs',joints:[8,9,10,11],weight:.30},
 {id:'torso',label:'Torso',joints:[0,1,6,7],weight:.10},
] as const;
const JOINT_NAMES=['Left shoulder','Right shoulder','Tossing elbow','Hitting elbow','Tossing wrist','Hitting wrist','Left hip','Right hip','Left knee','Right knee','Left ankle','Right ankle'];
const PHASE_NAMES=['preparation','upward swing','follow-through'];
const CONFIDENCE=.5, MAX_GAP=.18;
const mid=(a:number[],b:number[])=>[(a[0]+b[0])/2,(a[1]+b[1])/2];
const dist=(a:number[],b:number[])=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const visible=(p:PoseFrame,i:number)=>p.scores[i]>=CONFIDENCE&&p.xy[i]?.length>=2&&p.xy[i].slice(0,2).every(Number.isFinite);
const torso=(p:PoseFrame)=>dist(mid(p.xy[5],p.xy[6]),mid(p.xy[11],p.xy[12]));
const anchors=(p:PoseFrame)=>[5,6,11,12].every(i=>visible(p,i))&&torso(p)>10;
const unavailable=(reason:string):MotionSimilarity=>({status:'unavailable',reason});
// The 0.6 torso-length falloff is a provisional display scale, not an accuracy calibration.
const displayScore=(distance:number)=>Math.round(100*Math.exp(-distance/.6));

/** Does not extrapolate an aligned serve into walk-in, walk-out, or unobserved footage. */
export function referencePhaseAt(alignment:MotionAlignment,time:number):number|null {
 if(!Number.isFinite(time)||!alignment.length||time<alignment[0].time||time>alignment.at(-1)!.time)return null;
 const i=alignment.findIndex(p=>p.time>=time);if(i===0)return alignment[0].referencePhase;
 const a=alignment[i-1],b=alignment[i];return a.referencePhase+(b.referencePhase-a.referencePhase)*(time-a.time)/(b.time-a.time);
}
function interpolate(frames:PoseFrame[],time:number):PoseFrame|null {
 const i=frames.findIndex(p=>p.time>=time-1e-8);if(i<0)return null;
 const b=frames[i];if(Math.abs(b.time-time)<1e-8)return b;
 if(i===0)return null;const a=frames[i-1];if(b.time-a.time>MAX_GAP)return null;
 const q=(time-a.time)/(b.time-a.time);
 return {time,xy:a.xy.map((p,j)=>p.map((v,k)=>v+(b.xy[j][k]-v)*q)),scores:a.scores.map((s,j)=>Math.min(s,b.scores[j]))};
}
/** Brief confidence dips can use remaining visible joints, bounded by reliable poses.
 * Hip anchors must remain visible: both alignment and scoring are hip-relative.
 * Low-confidence coordinates are still excluded by normalized()/regionDistance(). */
function phaseTracked(samples:(PoseFrame|null)[]):boolean {
 let lastReliable:PoseFrame|null=null,gap=false;
 for(const p of samples){
  if(!p||!visible(p,11)||!visible(p,12))return false;
  const reliable=anchors(p)&&JOINTS.filter(([j])=>visible(p,j)).length>=8;
  if(reliable){
   if(gap&&(!lastReliable||p.time-lastReliable.time>MAX_GAP+1e-8))return false;
   lastReliable=p;gap=false;
  }else{
   if(!lastReliable||p.time-lastReliable.time>MAX_GAP+1e-8)return false;
   gap=true;
  }
 }
 return !gap;
}
/** Matches processor/capture.py MotionFinish; the pose fixture pins browser/offline parity. */
function observedFinish(frames:PoseFrame[],load:number,reach:number):number|null {
 const bodyIds=[5,6,11,12];
 let lastTime:number|null=null,lastBody:number|null=null,overheadSince:number|null=null;
 let sawOverhead=false,peakWrist=-Infinity,peakElbow=-Infinity;
 let anchor:PoseFrame|null=null,anchorScale=0,loweredSince:number|null=null,lastLowered:number|null=null;
 let observed=0,wasLowered=false,follow=false;
 for(const p of frames.filter(p=>p.time>=Math.max(load,reach-.4))){
  let dt=lastTime===null?0:p.time-lastTime;
  if(dt>.5+1e-9||(lastBody!==null&&p.time-lastBody>.5+1e-9)){
   lastBody=overheadSince=null;sawOverhead=false;peakWrist=peakElbow=-Infinity;
   anchor=null;anchorScale=0;loweredSince=lastLowered=null;observed=0;wasLowered=follow=false;dt=0;
  }
  lastTime=p.time;
  const lengths=[[5,11],[6,12]].filter(([a,b])=>visible(p,a)&&visible(p,b)).map(([a,b])=>dist(p.xy[a],p.xy[b]));
  if(bodyIds.filter(j=>visible(p,j)).length<3||!lengths.length){wasLowered=false;overheadSince=null;continue;}
  const scale=lengths.reduce((sum,v)=>sum+v,0)/lengths.length;
  if(scale<=1e-6){wasLowered=false;overheadSince=null;continue;}
  lastBody=p.time;
  const height=(j:number)=>visible(p,6)&&visible(p,j)?(p.xy[6][1]-p.xy[j][1])/scale:null;
  const wrist=height(10),elbow=height(8);
  const overhead=(wrist!==null&&wrist>=.5)||(wrist===null&&elbow!==null&&elbow>=.25);
  if(overhead){
   overheadSince??=p.time;
   if(wrist!==null&&wrist>peakWrist){peakWrist=wrist;anchor=p;anchorScale=scale;}
   if(elbow!==null&&elbow>peakElbow){peakElbow=elbow;if(!anchor){anchor=p;anchorScale=scale;}}
   if(p.time-overheadSince>=.03-1e-9)sawOverhead=true;
   loweredSince=lastLowered=null;observed=0;wasLowered=false;continue;
  }
  overheadSince=null;if(!sawOverhead||!anchor)continue;
  const common=bodyIds.filter(j=>visible(p,j)&&visible(anchor!,j));
  const shift=common.length>=2?Math.max(...common.map(j=>dist(p.xy[j],anchor!.xy[j])))/anchorScale:0;
  const wristDown=wrist!==null&&peakWrist>=.5&&peakWrist-wrist>=.4&&wrist<.1;
  const elbowDown=elbow!==null&&peakElbow>=.2&&peakElbow-elbow>=.35&&elbow<-.1&&(wrist===null||wrist<.5)&&shift>=.08;
  if(lastLowered!==null&&p.time-lastLowered>.5+1e-9){loweredSince=null;observed=0;}
  if(!wristDown&&!elbowDown){wasLowered=false;continue;}
  loweredSince??=p.time;if(wasLowered)observed+=dt;wasLowered=true;lastLowered=p.time;
  if(!follow&&observed>=.1-1e-9){follow=true;continue;}
  if(follow&&observed>=.2-1e-9&&p.time-loweredSince>=.3-1e-9)return p.time;
 }
 return null;
}
function boundaries(input:MotionInput,load:number,reach:number,size:number):[number|null,number|null] {
 const {frames,stages=[]}=input;
 const setup=stages.find(s=>s.id==='setup'&&s.status==='estimated');
 const finish=stages.find(s=>s.id==='finish'&&s.status==='estimated');
 let start=setup?.time??null,end=finish?.end??null;
 // Older results have no stage records. Find a visible preparatory arm rise, keeping its low-arm start.
 if(start===null){
  let low:PoseFrame|null=null;
  for(const p of frames.filter(p=>p.time>=load-2.5&&p.time<load)){
   if(!anchors(p)||!visible(p,9)){low=null;continue;}
   const height=(mid(p.xy[5],p.xy[6])[1]-p.xy[9][1])/size;
   if(height<.1)low=p;
   if(height>.4&&low&&p.time-low.time>=.1){start=low.time;break;}
  }
 }
 // Use exactly the offline/live finish cues when older results lack stage metadata.
 if(end===null)end=observedFinish(frames,load,reach);
 return [start!==null&&Number.isFinite(start)&&start>=frames[0].time&&start<load-.1?start:null,end!==null&&Number.isFinite(end)&&end<=Math.min(input.duration,frames.at(-1)!.time)&&reach<end-.1?end:null];
}

type Weighting={visible:(p:PoseFrame,j:number)=>boolean;weight:(p:PoseFrame,j:number)=>number;empty:number;note:string};
const STRICT:Weighting={visible,weight:(p,j)=>Math.min(1,p.scores[j]),empty:Infinity,note:'uncertain samples excluded'};
const hasXY=(p:PoseFrame,j:number)=>p.xy[j]?.length>=2&&p.xy[j].slice(0,2).every(Number.isFinite);
// Lenient joints are never dropped, only down-weighted by tracking score, so a number always exists.
const LENIENT:Weighting={visible:hasXY,weight:(p,j)=>Math.max(.01,Math.min(1,Number.isFinite(p.scores[j])?p.scores[j]:0)),empty:0,note:'low-confidence samples down-weighted'};
const PHASES=[0,40,80,100];
type Totals={alignment:MotionAlignment;totalError:number;totalWeight:number;regionTotals:{sum:number;weight:number}[];regionCoverage:RegionCoverage;phaseScores:PhaseScore[];excludedMeasurements:string[]};
const totals=():Totals=>({alignment:[],totalError:0,totalWeight:0,regionTotals:REGIONS.map(()=>({sum:0,weight:0})),regionCoverage:{hittingArm:0,tossingArm:0,legs:0,torso:0},phaseScores:[],excludedMeasurements:[]});
/** Anchored DTW of one phase onto reference phases, then region errors along the path; false when no path fits the band. */
function scorePhase(sampled:PoseFrame[],segment:number,times:number[],reference:number[][][],refPose:(p:number[][])=>number[][],projected:number[][][],size:number,w:Weighting,acc:Totals):boolean {
 const from=PHASES[segment],to=PHASES[segment+1],n=to-from+1,phaseWeight=(to-from)/100;
 for(const[k,[j]]of JOINTS.entries()){
  if(sampled.some(p=>!visible(p,j)))acc.excludedMeasurements.push(`${JOINT_NAMES[k]} partly hidden during ${PHASE_NAMES[segment]}; ${w.note}.`);
 }
 for(const region of REGIONS)acc.regionCoverage[region.id]+=phaseWeight*sampled.reduce((sum,p)=>sum+region.joints.filter(k=>visible(p,JOINTS[k][0])).length/region.joints.length,0)/n;
 const user=sampled.map(p=>{const root=mid(p.xy[11],p.xy[12]);return JOINTS.map(([j])=>w.visible(p,j)?[(p.xy[j][0]-root[0])/size,(p.xy[j][1]-root[1])/size]:null);});
 const regionDistance=(i:number,pose:number[][],keys:readonly number[])=>{
  let sum=0,confidence=0;
  for(const k of keys)if(user[i][k]){const weight=w.weight(sampled[i],JOINTS[k][0]);sum+=dist(user[i][k]!,pose[k])**2*weight;confidence+=weight;}
  return confidence?{error:Math.sqrt(sum/confidence),confidence:confidence/keys.length}:null;
 };
 const poseDistance=(i:number,pose:number[][])=>{
  let sum=0,weight=0;
  for(const region of REGIONS){const d=regionDistance(i,pose,region.joints);if(d){sum+=d.error*region.weight;weight+=region.weight;}}
  return weight?sum/weight:w.empty;
 };
 const distance=(i:number,j:number)=>poseDistance(i,projected[from+j]);
 // Anchored DTW: a 20% band per phase, at most 2:1 local stretch; neither end can be skipped.
 const cost=Array.from({length:n},()=>Array(n).fill(Infinity)),prev=Array.from({length:n},()=>Array<[number,number]|null>(n).fill(null));
 cost[0][0]=distance(0,0);
 for(let i=1;i<n;i++)for(let j=1;j<n;j++){
  if(Math.abs(i-j)>Math.ceil((n-1)*.2))continue;
  for(const [di,dj]of [[1,1],[1,2],[2,1]]){
   if(i<di||j<dj)continue;
   const skipped=di===2?distance(i-1,j):dj===2?distance(i,j-1):0;
   const c=cost[i-di][j-dj]+distance(i,j)+skipped+.002*(di+dj-2);
   if(c<cost[i][j]){cost[i][j]=c;prev[i][j]=[i-di,j-dj];}
  }
 }
 if(!Number.isFinite(cost[n-1][n-1]))return false;
 const path:[number,number][]=[];let point:[number,number]|null=[n-1,n-1];
 while(point){path.push(point);point=prev[point[0]][point[1]];}path.reverse();
 const map=Array<number>(n);for(const[i,j]of path)map[i]=j;
 for(let i=1;i<n-1;i++)if(map[i]===undefined)map[i]=(map[i-1]+map[i+1])/2;
 const regionErrors=REGIONS.map(()=>({sum:0,confidence:0}));
 for(let i=0;i<n;i++){
  const phase=from+map[i];if(acc.alignment.length===0||i>0)acc.alignment.push({time:sampled[i].time,referencePhase:phase});
  const pose=refPose(referencePoseAt(reference,phase)!);
  for(const[r,region]of REGIONS.entries()){
   const d=regionDistance(i,pose,region.joints);
   if(d){regionErrors[r].sum+=d.error*d.confidence;regionErrors[r].confidence+=d.confidence;}
  }
 }
 let phaseError=0,phaseRegionWeight=0;
 for(const[r,region]of REGIONS.entries()){
  const d=regionErrors[r];
  if(d.confidence){const e=d.sum/d.confidence;acc.totalError+=phaseWeight*region.weight*e;acc.totalWeight+=phaseWeight*region.weight;acc.regionTotals[r].sum+=phaseWeight*e;acc.regionTotals[r].weight+=phaseWeight;phaseError+=region.weight*e;phaseRegionWeight+=region.weight;}
 }
 acc.phaseScores.push({phase:PHASE_NAMES[segment],start:times[segment],end:times[segment+1],score:phaseRegionWeight?displayScore(phaseError/phaseRegionWeight):null});
 return true;
}
function finish(acc:Totals,fit:Fit,quality:'full'|'partial'|'low',warnings:string[],method:string):MotionSimilarity {
 for(const r of REGIONS)acc.regionCoverage[r.id]=Math.max(0,Math.min(1,acc.regionCoverage[r.id]));
 const coverage=Math.max(0,Math.min(1,REGIONS.reduce((sum,r)=>sum+r.weight*acc.regionCoverage[r.id],0)));
 const meanDistance=acc.totalError/acc.totalWeight;
 const regionScores=Object.fromEntries(REGIONS.map((r,i)=>[r.id,acc.regionTotals[i].weight?displayScore(acc.regionTotals[i].sum/acc.regionTotals[i].weight):null])) as RegionScores;
 return {status:'available',score:displayScore(meanDistance),alignment:acc.alignment,fit,meanDistance,coverage,quality,warnings,excludedMeasurements:acc.excludedMeasurements,regionCoverage:acc.regionCoverage,regionScores,phaseScores:acc.phaseScores,method};
}
const validReference=(reference:number[][][])=>Array.isArray(reference)&&reference.length===101&&reference.every(p=>Array.isArray(p)&&p.length===17&&p.every(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite)));

/** Rear-view, right-handed comparison with every tracking gate; the reason explains a withheld strict score. */
function strictMotion(input:MotionInput):MotionSimilarity {
 const {frames,reference,events,duration}=input;
 if(!Number.isFinite(duration)||duration<=0||frames.length<10||frames.some((p,i)=>!Number.isFinite(p.time)||(i>0&&p.time<=frames[i-1].time)||p.xy.length!==17||p.scores.length!==17||p.xy.some(q=>!Array.isArray(q)||q.length<2)))return unavailable('Recording timestamps or pose data are invalid.');
 const load=events.find(e=>e.id==='loading')?.time,reach=events.find(e=>e.id==='reach')?.time;
 if(load===undefined||reach===undefined||![load,reach].every(Number.isFinite)||!(0<load&&load<reach&&reach<duration))return unavailable('Reliable loading and overhead-reach moments are needed to align the motion.');
 const loadFrame=interpolate(frames,load),reachFrame=interpolate(frames,reach);
 if(!loadFrame||!anchors(loadFrame)||!reachFrame||!anchors(reachFrame)||!visible(reachFrame,10))return unavailable('Torso or hitting-arm tracking is uncertain at the phase anchors.');
 const fit=fitReference(reference[40],loadFrame);if(!fit)return unavailable('The torso could not be fitted to the selected reference.');
 const size=torso(loadFrame);
 if((mid(reachFrame.xy[5],reachFrame.xy[6])[1]-reachFrame.xy[10][1])/size<.25)return unavailable('A clear overhead reach is needed for a complete serve comparison.');
 const [start,end]=boundaries(input,load,reach,size);
 if(start===null||end===null)return unavailable(start===null&&end===null?'The setup and follow-through could not be identified reliably in this recording.'
  :start===null?'The setup before loading could not be identified reliably in this recording.':'The follow-through / finish could not be identified reliably in this recording.');
 const inWindow=frames.filter(p=>p.time>=start&&p.time<=end);
 if(inWindow.some((p,i)=>i>0&&p.time-inWindow[i-1].time>MAX_GAP))return unavailable('Tracking has a long gap within the serve.');
 const refPose=(p:number[][])=>{const q=projectPose(p,0),root=mid(q[4],q[1]);return JOINTS.map(([,j])=>[(q[j][0]-root[0])*fit.scale/size,(q[j][1]-root[1])*fit.scale/size]);};
 const projected=reference.map(refPose),times=[start,load,reach,end],acc=totals();
 for(let segment=0;segment<3;segment++){
  const n=PHASES[segment+1]-PHASES[segment]+1;
  const sampled=Array.from({length:n},(_,i)=>interpolate(frames,times[segment]+(times[segment+1]-times[segment])*i/(n-1)));
  if(!phaseTracked(sampled))return unavailable('A movement phase has insufficient joint tracking to align it reliably.');
  for(const region of REGIONS){
   // At least half of each dynamic region must be observed within the phase.
   // A missing wrist is tolerable; a missing entire hitting arm is not replaced with torso similarity.
   if(sampled.filter(p=>region.joints.some(k=>visible(p!,JOINTS[k][0]))).length/n<.5)return unavailable(`${region.label} is not observed enough during ${PHASE_NAMES[segment]} to compare the motion.`);
  }
  if(!scorePhase(sampled as PoseFrame[],segment,times,reference,refPose,projected,size,STRICT,acc))return unavailable('The phases could not be aligned within the allowed timing difference.');
 }
 return finish(acc,fit,acc.excludedMeasurements.length?'partial':'full',[],'experimental-rear-pose-dtw-v2');
}

const SWAP=[0,2,1,4,3,6,5,8,7,10,9,12,11,14,13,16,15];
type Orientation={yaw:number;mirror:boolean;swap:boolean};
/** Rear reference seen from the given camera view; a left-hander is a mirrored, relabelled right-hander. */
function orientations(view:string,handedness:string):Orientation[] {
 const views:[number,boolean][]=view==='rear'?[[0,false]]:view==='front'?[[0,true]]:view==='side'?[[90,false],[-90,false]]:[[0,false],[0,true],[90,false],[-90,false]];
 const hands=handedness==='left'?[true]:handedness==='right'?[false]:[false,true];
 return hands.flatMap(swap=>views.map(([yaw,mirror])=>({yaw,mirror:mirror!==swap,swap})));
}
const orient=(p:PoseFrame,o:Orientation):PoseFrame=>{
 const xy=o.swap?SWAP.map(j=>p.xy[j]):p.xy,scores=o.swap?SWAP.map(j=>p.scores[j]):p.scores;
 return {time:p.time,xy:o.mirror?xy.map(q=>[-q[0],q[1]]):xy,scores};
};
/** Bracketing frames regardless of gap length; lenient mode never leaves a sample empty. */
function interpolateAny(frames:PoseFrame[],time:number):PoseFrame {
 const i=frames.findIndex(p=>p.time>=time-1e-8);if(i<=0)return i<0?frames.at(-1)!:frames[0];
 const a=frames[i-1],b=frames[i],q=(time-a.time)/(b.time-a.time);
 return {time,xy:a.xy.map((p,j)=>p.map((v,k)=>v+(b.xy[j][k]-v)*q)),scores:a.scores.map((s,j)=>Math.min(s,b.scores[j]))};
}
/** Highest hitting wrist (after the opening frames), then the lowest hips within 1.5 s before it. */
function estimateAnchors(frames:PoseFrame[],size:number):[number,number] {
 const t0=frames[0].time,tN=frames.at(-1)!.time,height=(p:PoseFrame)=>(mid(p.xy[5],p.xy[6])[1]-p.xy[10][1])/size;
 let candidates=frames.filter(p=>p.time>=t0+Math.min(.2,(tN-t0)/4));
 for(const min of [.3,.1]){const c=candidates.filter(p=>p.scores[10]>=min);if(c.length){candidates=c;break;}}
 const reach=candidates.reduce((a,b)=>height(b)>height(a)?b:a).time;
 const before=frames.filter(p=>p.time<reach-.1&&p.time>=reach-1.5),window=before.length?before:frames.filter(p=>p.time<reach);
 if(!window.length)return [t0,tN];
 return [window.reduce((a,b)=>mid(b.xy[11],b.xy[12])[1]>mid(a.xy[11],a.xy[12])[1]?b:a).time,reach];
}
function weightedMedian(values:{v:number;w:number}[]):number {
 const sorted=[...values].sort((a,b)=>a.v-b.v),half=sorted.reduce((s,x)=>s+x.w,0)/2;let sum=0;
 for(const x of sorted){sum+=x.w;if(sum>=half)return x.v;}return sorted.at(-1)!.v;
}
function lenientFor(input:MotionInput,frames:PoseFrame[],o:Orientation):(MotionSimilarity&{status:'available'})|null {
 const f=frames.map(p=>orient(p,o)),t0=f[0].time,tN=f.at(-1)!.time,warnings:string[]=[];
 const sizes=f.map(p=>({v:torso(p),w:Math.min(...[5,6,11,12].map(j=>LENIENT.weight(p,j)))})).filter(x=>Number.isFinite(x.v)&&x.v>1e-6);
 if(!sizes.length)return null;
 const size=weightedMedian(sizes);
 let load=input.events.find(e=>e.id==='loading')?.time,reach=input.events.find(e=>e.id==='reach')?.time;
 if(load===undefined||reach===undefined||!(t0<=load&&load<reach&&reach<=tN)){
  [load,reach]=estimateAnchors(f,size);warnings.push('Loading and reach were estimated from the highest hitting wrist and lowest hip position.');
 }
 const stage=(id:string)=>input.stages?.find(s=>s.id===id&&s.status==='estimated');
 const setup=stage('setup')?.time,finishEnd=stage('finish')?.end;
 const start=setup!=null&&setup>=t0&&setup<load-.1?setup:Math.max(t0,load-1.2),end=finishEnd!=null&&finishEnd<=tN&&finishEnd>reach+.1?finishEnd:Math.min(tN,reach+.6);
 const q=projectPose(input.reference[40],o.yaw),refTorso=dist(mid(q[11],q[14]),mid(q[4],q[1]));
 if(!(refTorso>.05))return null;
 const fit:Fit={yaw:o.yaw,mirror:o.mirror,scale:size/refTorso,error:0};
 const refPose=(p:number[][])=>{const r=projectPose(p,o.yaw),root=mid(r[4],r[1]);return JOINTS.map(([,j])=>[(r[j][0]-root[0])*fit.scale/size,(r[j][1]-root[1])*fit.scale/size]);};
 const projected=input.reference.map(refPose),times=[start,load,reach,end],acc=totals();
 for(let segment=0;segment<3;segment++){
  if(times[segment+1]-times[segment]<.1){warnings.push(segment===0?'The setup before loading was not recorded; it is not scored.':'The follow-through was not recorded; it is not scored.');continue;}
  const n=PHASES[segment+1]-PHASES[segment]+1;
  const sampled=Array.from({length:n},(_,i)=>interpolateAny(f,times[segment]+(times[segment+1]-times[segment])*i/(n-1)));
  scorePhase(sampled,segment,times,input.reference,refPose,projected,size,LENIENT,acc);
 }
 if(!acc.totalWeight)return null;
 return finish(acc,fit,'low',warnings,'experimental-pose-dtw-lenient-v1') as MotionSimilarity&{status:'available'};
}

/** Experimental 2-D body-shape similarity, not serve quality or a calibrated percentage.
 * The strict rear-view score is used when every tracking gate passes; otherwise a confidence-weighted
 * lenient score is returned with quality 'low' and the reasons, so any tracked recording gets a number. */
export function compareMotion(input:MotionInput):MotionSimilarity {
 if(!validReference(input.reference))return unavailable('The selected reference contains invalid pose data.');
 const strict=input.view==='rear'&&input.handedness==='right'?strictMotion(input):null;
 if(strict?.status==='available')return strict;
 const frames=(Array.isArray(input.frames)?input.frames:[]).filter(p=>Number.isFinite(p?.time)&&p.xy?.length===17&&p.scores?.length===17&&p.xy.every(q=>Array.isArray(q)&&q.length>=2))
  .filter((p,i,all)=>i===0||p.time>all[i-1].time);
 if(frames.length<2)return unavailable('No tracked body poses were recorded.');
 let best:(MotionSimilarity&{status:'available'})|null=null;
 for(const o of orientations(input.view,input.handedness)){const r=lenientFor(input,frames,o);if(r&&(!best||r.meanDistance<best.meanDistance))best=r;}
 if(!best)return unavailable('No tracked body poses were recorded.');
 best.warnings.unshift(strict?.status==='unavailable'?strict.reason:'The reference set is filmed from behind a right-handed server; this recording was re-oriented to match it.');
 return best;
}

/** Shared fractional pose sampler for the rendered overlay and its score. */
export function referencePoseAt(reference:number[][][],phase:number):number[][]|null {
 if(!Number.isFinite(phase)||phase<0||phase>100||reference.length!==101)return null;
 const lo=Math.floor(phase),hi=Math.ceil(phase),mix=phase-lo,a=reference[lo],b=reference[hi];
 if(!a||!b||a.length!==17||b.length!==17||[a,b].some(p=>p.some(v=>v.length!==3||!v.every(Number.isFinite))))return null;
 return a.map((p,j)=>p.map((v,k)=>v*(1-mix)+b[j][k]*mix));
}
