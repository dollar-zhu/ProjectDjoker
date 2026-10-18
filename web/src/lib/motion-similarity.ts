import {projectPose} from './reference';
import {fitReference,type Fit,type PoseFrame} from './overlay';

export type MotionAlignment = {time:number;referencePhase:number}[];
export type RegionCoverage = {hittingArm:number;tossingArm:number;legs:number;torso:number};
type Stage = {id:string;status:string;time:number|null;start:number|null;end:number|null};
export type MotionInput = {frames:PoseFrame[];reference:number[][][];events:{id:string;time:number}[];duration:number;view:string;handedness:string;stages?:Stage[]};
export type MotionSimilarity = {status:'unavailable';reason:string;alignment?:MotionAlignment;fit?:Fit;coverage?:number} | {status:'available';score:number;alignment:MotionAlignment;fit:Fit;meanDistance:number;coverage:number;quality:'full'|'partial';excludedMeasurements:string[];regionCoverage:RegionCoverage;method:string};
// COCO left/right correspondences are identical to the rear overlay. No yaw or mirror search.
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

/** Experimental 2-D body-shape similarity, not serve quality or a calibrated percentage. */
export function compareMotion(input:MotionInput):MotionSimilarity {
 const {frames,reference,events,duration,view,handedness}=input;
 if(view!=='rear'||handedness!=='right')return unavailable('Use a rear-view, right-handed serve for this reference set.');
 if(!Array.isArray(reference)||reference.length!==101||reference.some(p=>!Array.isArray(p)||p.length!==17||p.some(v=>!Array.isArray(v)||v.length!==3||!v.every(Number.isFinite))))return unavailable('The selected reference contains invalid pose data.');
 if(!Number.isFinite(duration)||duration<=0||frames.length<10||frames.some((p,i)=>!Number.isFinite(p.time)||(i>0&&p.time<=frames[i-1].time)||p.xy.length!==17||p.scores.length!==17||p.xy.some(q=>!Array.isArray(q)||q.length<2)))return unavailable('Recording timestamps or pose data are invalid.');
 const load=events.find(e=>e.id==='loading')?.time,reach=events.find(e=>e.id==='reach')?.time;
 if(load===undefined||reach===undefined||![load,reach].every(Number.isFinite)||!(0<load&&load<reach&&reach<duration))return unavailable('Reliable loading and overhead-reach moments are needed to align the motion.');
 const loadFrame=interpolate(frames,load),reachFrame=interpolate(frames,reach);
 if(!loadFrame||!anchors(loadFrame)||!reachFrame||!anchors(reachFrame)||!visible(reachFrame,10))return unavailable('Torso or hitting-arm tracking is uncertain at the phase anchors.');
 const fit=fitReference(reference[40],loadFrame);if(!fit)return unavailable('The torso could not be fitted to the selected reference.');
 const size=torso(loadFrame);
 if((mid(reachFrame.xy[5],reachFrame.xy[6])[1]-reachFrame.xy[10][1])/size<.25)return unavailable('A clear overhead reach is needed for a complete serve comparison.');
 const [start,end]=boundaries(input,load,reach,size);
 let reason=start===null||end===null?'A complete setup and observed follow-through/finish are needed; record the whole serve.':'';
 const inWindow=frames.filter(p=>p.time>=(start??load)&&p.time<=(end??reach));
 if(inWindow.some((p,i)=>i>0&&p.time-inWindow[i-1].time>MAX_GAP))return unavailable('Tracking has a long gap within the serve.');
 const counts=JOINTS.map(([j])=>inWindow.filter(p=>visible(p,j)).length/inWindow.length);
 let coverage=counts.reduce((a,b)=>a+b,0)/counts.length;
 const normalizeReference=(p:number[][])=>{const q=projectPose(p,0),root=mid(q[4],q[1]);return JOINTS.map(([,j])=>[(q[j][0]-root[0])*fit.scale/size,(q[j][1]-root[1])*fit.scale/size]);};
 const projected=reference.map(normalizeReference);
 const normalized=(p:PoseFrame)=>{const root=mid(p.xy[11],p.xy[12]);return JOINTS.map(([j])=>visible(p,j)?[(p.xy[j][0]-root[0])/size,(p.xy[j][1]-root[1])/size]:null);};
 const alignment:MotionAlignment=[];let totalError=0,totalWeight=0;
 const excludedMeasurements:string[]=[];
 const regionCoverage:RegionCoverage={hittingArm:0,tossingArm:0,legs:0,torso:0};
 const times=[start??load,load,reach,end??reach],phases=[0,40,80,100];
 for(let segment=0;segment<3;segment++){
  if((segment===0&&start===null)||(segment===2&&end===null))continue;
  const from=phases[segment],to=phases[segment+1],n=to-from+1;
  const sampled=Array.from({length:n},(_,i)=>interpolate(frames,times[segment]+(times[segment+1]-times[segment])*i/(n-1)));
  if(!phaseTracked(sampled)){reason||='A movement phase has insufficient joint tracking to align it reliably.';break;}
  const phaseWeight=(to-from)/100;
  for(const[k,[j]]of JOINTS.entries()){
   if(sampled.some(p=>!visible(p!,j)))excludedMeasurements.push(`${JOINT_NAMES[k]} partly hidden during ${PHASE_NAMES[segment]}; uncertain samples excluded.`);
  }
  for(const region of REGIONS){
   const observed=sampled.filter(p=>region.joints.some(k=>visible(p!,JOINTS[k][0]))).length/n;
   // At least half of each dynamic region must be observed within the phase.
   // A missing wrist is tolerable; a missing entire hitting arm is not replaced with torso similarity.
   if(observed<.5)reason||=`${region.label} is not observed enough during ${PHASE_NAMES[segment]} to compare the motion.`;
   regionCoverage[region.id]+=phaseWeight*sampled.reduce((sum,p)=>sum+region.joints.filter(k=>visible(p!,JOINTS[k][0])).length/region.joints.length,0)/n;
  }
  const user=sampled.map(p=>normalized(p!));
  const regionDistance=(i:number,pose:number[][],keys:readonly number[])=>{
   let sum=0,confidence=0;
   for(const k of keys)if(user[i][k]){const weight=Math.min(1,sampled[i]!.scores[JOINTS[k][0]]);sum+=dist(user[i][k]!,pose[k])**2*weight;confidence+=weight;}
   return confidence?{error:Math.sqrt(sum/confidence),confidence:confidence/keys.length}:null;
  };
  const poseDistance=(i:number,pose:number[][])=>{
   let sum=0,weight=0;
   for(const region of REGIONS){const d=regionDistance(i,pose,region.joints);if(d){sum+=d.error*region.weight;weight+=region.weight;}}
   return weight?sum/weight:Infinity;
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
  if(!Number.isFinite(cost[n-1][n-1]))return unavailable('The phases could not be aligned within the allowed timing difference.');
  const path:[number,number][]=[];let point:[number,number]|null=[n-1,n-1];
  while(point){path.push(point);point=prev[point[0]][point[1]];}path.reverse();
  const map=Array<number>(n);for(const[i,j]of path)map[i]=j;
  for(let i=1;i<n-1;i++)if(map[i]===undefined)map[i]=(map[i-1]+map[i+1])/2;
  const regionErrors=REGIONS.map(()=>({sum:0,confidence:0}));
  for(let i=0;i<n;i++){
   const phase=from+map[i];if(alignment.length===0||i>0)alignment.push({time:sampled[i]!.time,referencePhase:phase});
   const pose=normalizeReference(referencePoseAt(reference,phase)!);
   for(const[r,region]of REGIONS.entries()){
    const d=regionDistance(i,pose,region.joints);
    if(d){regionErrors[r].sum+=d.error*d.confidence;regionErrors[r].confidence+=d.confidence;}
   }
  }
  for(const[r,region]of REGIONS.entries()){
   const d=regionErrors[r];
   if(d.confidence){totalError+=phaseWeight*region.weight*d.sum/d.confidence;totalWeight+=phaseWeight*region.weight;}
  }
 }
 for(const r of REGIONS)regionCoverage[r.id]=Math.max(0,Math.min(1,regionCoverage[r.id]));
 coverage=Math.max(0,Math.min(1,REGIONS.reduce((sum,r)=>sum+r.weight*regionCoverage[r.id],0)));
 if(reason)return {status:'unavailable',reason,...(alignment.length?{alignment,fit,coverage}:{})};
 const meanDistance=totalError/totalWeight;
 // The 0.6 torso-length falloff is a provisional display scale, not an accuracy calibration.
 return {status:'available',score:Math.round(100*Math.exp(-meanDistance/.6)),alignment,fit,meanDistance,coverage,quality:excludedMeasurements.length?'partial':'full',excludedMeasurements,regionCoverage,method:'experimental-rear-pose-dtw-v2'};
}

/** Shared fractional pose sampler for the rendered overlay and its score. */
export function referencePoseAt(reference:number[][][],phase:number):number[][]|null {
 if(!Number.isFinite(phase)||phase<0||phase>100||reference.length!==101)return null;
 const lo=Math.floor(phase),hi=Math.ceil(phase),mix=phase-lo,a=reference[lo],b=reference[hi];
 if(!a||!b||a.length!==17||b.length!==17||[a,b].some(p=>p.some(v=>v.length!==3||!v.every(Number.isFinite))))return null;
 return a.map((p,j)=>p.map((v,k)=>v*(1-mix)+b[j][k]*mix));
}
