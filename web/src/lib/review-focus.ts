import type {Stage} from './playback';

/** Body parts each serve stage (or coaching focus) is read from. COCO indices, right-handed; left-handed mirrors pairs.
 * joints light the body diagram's bones; marks (default: joints) are the ones circled on the video. */
export type BodyFocus={part:string;region:string;joints:number[];marks?:number[];look:string};
const FOCUS:Record<string,BodyFocus>={
 setup:{part:'Feet & stance',region:'Legs',joints:[15,16],look:'Stance width and stillness before the motion starts'},
 toss:{part:'Tossing arm',region:'Tossing arm',joints:[5,7,9],look:'How high the tossing wrist rises and when'},
 loading:{part:'Knees',region:'Legs',joints:[11,12,13,14,15,16],marks:[13,14],look:'Knee bend at the lowest point of the serve'},
 acceleration:{part:'Legs into hitting arm',region:'Legs',joints:[11,12,13,14,15,16,6,8,10],marks:[13,14,10],look:'How the knees straighten as the hitting arm drives up'},
 follow_through:{part:'Hitting arm',region:'Hitting arm',joints:[6,8,10],look:'The hitting arm coming down after the reach'},
 finish:{part:'Hips & balance',region:'Torso',joints:[11,12,15,16],look:'Recovery and balance after the swing'},
 recapture:{part:'Camera view',region:'Recording',joints:[],look:'Whether the recording shows enough of the movement'},
};
const MIRROR:Record<number,number>={5:6,6:5,7:8,8:7,9:10,10:9,11:12,12:11,13:14,14:13,15:16,16:15};
export function bodyFocus(id:string|null|undefined,handedness='right'):BodyFocus|null {
 const f=id?FOCUS[id]:undefined;if(!f)return null;
 const mirror=(js:number[])=>js.map(j=>MIRROR[j]??j);
 return handedness==='left'?{...f,joints:mirror(f.joints),marks:f.marks&&mirror(f.marks)}:f;
}

const MEASURES:Record<string,{label:string;unit:'deg'|'delta'|'torso'|'s'}>={
 left_knee_deg:{label:'Left knee',unit:'deg'},right_knee_deg:{label:'Right knee',unit:'deg'},
 mean_knee_change_deg:{label:'Knee extension',unit:'delta'},wrist_rise_torso_lengths:{label:'Wrist rise',unit:'torso'},
 ankle_spacing_torso_lengths:{label:'Stance width',unit:'torso'},body_recovery_shift_torso_lengths:{label:'Body shift',unit:'torso'},
 wrist_descent_torso_lengths:{label:'Wrist drop',unit:'torso'},elbow_descent_torso_lengths:{label:'Elbow drop',unit:'torso'},
 observed_descent_seconds:{label:'Descent',unit:'s'},playback_duration_s:{label:'Duration',unit:'s'},
};
/** Labels a stored stage measurement for display; torso lengths are body-relative, not centimetres. */
export function formatMeasurement(key:string,value:number):{label:string;value:string;hint?:string} {
 const m=MEASURES[key],label=m?.label||key.replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());
 if(!Number.isFinite(value))return {label,value:'—'};
 switch(m?.unit){
  case 'deg':return {label,value:`${Math.round(value)}°`};
  case 'delta':return {label,value:`${value>0?'+':''}${Math.round(value)}°`};
  case 'torso':return {label,value:`${value.toFixed(2)}×`,hint:'torso lengths'};
  case 's':return {label,value:`${value.toFixed(2)} s`};
  default:return {label,value:String(Math.round(value*100)/100)};
 }
}

/** Visible review window: the estimated stages plus padding, so walk-in and walk-out footage don't dominate the scrubber. */
export function reviewWindow(stages:Pick<Stage,'start'|'end'|'status'>[],duration:number,pad=.35):[number,number] {
 const known=stages.filter(s=>s.status==='estimated'&&Number.isFinite(s.start)&&Number.isFinite(s.end));
 if(!known.length||!(duration>0))return [0,Math.max(duration,0)];
 const from=Math.max(0,Math.min(...known.map(s=>s.start!))-pad),to=Math.min(duration,Math.max(...known.map(s=>s.end!))+pad);
 return to>from?[from,to]:[0,duration];
}

/** Greedy lane packing; body stages can overlap (e.g. toss and loading). */
export function stageLanes<T extends Pick<Stage,'start'|'end'>>(stages:T[]):{stage:T;lane:number}[] {
 const ends:number[]=[];
 return [...stages].filter(s=>Number.isFinite(s.start)&&Number.isFinite(s.end)).sort((a,b)=>a.start!-b.start!).map(stage=>{
  let lane=ends.findIndex(e=>e<=stage.start!+1e-6);if(lane<0){lane=ends.length;ends.push(0);}ends[lane]=stage.end!;return {stage,lane};
 });
}
