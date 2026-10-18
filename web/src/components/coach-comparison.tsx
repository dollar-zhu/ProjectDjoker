'use client';
import {useEffect,useMemo,useState,type ReactNode} from 'react';
import {compareMotion,type RegionScores} from '@/lib/motion-similarity';
import {BodyMap} from '@/components/movement-review';
import {scoreColor} from '@/components/serve-timeline';
import type {PoseFrame,ReferenceOverlay} from '@/lib/overlay';
import type {Stage} from '@/lib/playback';

const REGIONS:{id:keyof RegionScores;label:string;joints:number[]}[]=[{id:'hittingArm',label:'Hitting arm',joints:[6,8,10]},{id:'tossingArm',label:'Tossing arm',joints:[5,7,9]},{id:'legs',label:'Legs',joints:[11,12,13,14,15,16]},{id:'torso',label:'Torso',joints:[5,6,11,12]}];
/** Per-body-part similarity; the lowest one is called out because it is where the overlay differs most. */
function RegionBreakdown({scores,handedness}:{scores:RegionScores;handedness:string}){
 const rows=REGIONS.map(r=>({...r,score:scores[r.id]})),scored=rows.filter(r=>r.score!==null),low=scored.length>1?scored.reduce((a,b)=>b.score!<a.score!?b:a):null;
 const mirror=(j:number)=>handedness==='left'&&j>=5?(j%2?j+1:j-1):j;
 return <div className="region-breakdown">
  <BodyMap joints={(low?.joints||[]).map(mirror)} label={low?.label||'no single body part'} size="sm"/>
  <div><span className="eyebrow">BY BODY PART</span>{rows.map(r=><div key={r.id} className={`region-row ${low?.id===r.id?'low':''}`}><span>{r.label}</span><i><b style={{width:`${r.score??0}%`,background:scoreColor(r.score)}}/></i><em>{r.score??'—'}</em></div>)}{low&&<p>Biggest difference: <strong>{low.label.toLowerCase()}</strong></p>}</div>
 </div>;
}
type Reference={player:string;poses:number[][][];selected:string;serves:{id:string;opponent:string}[];source:string;license:string};
export function CoachComparison({view,handedness,duration,events,frames,stages,onOverlayChange,children}:{view:string;handedness:string;duration:number;events:{id:string;time:number}[];frames:PoseFrame[];stages?:Stage[];onOverlayChange:(overlay:ReferenceOverlay|null,play?:boolean)=>void;children:ReactNode}){
 const [player,setPlayer]=useState('djokovic'),[type,setType]=useState('1'),[serve,setServe]=useState('');
 const [data,setData]=useState<Reference|null>(null),[error,setError]=useState('');
 useEffect(()=>{
  const controller=new AbortController();setData(null);setError('');
  fetch(`/api/references?player=${player}&type=${type}${serve?'&serve='+encodeURIComponent(serve):''}`,{signal:controller.signal}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||'Could not load reference.');return d;}).then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>controller.abort();
 },[player,type,serve]);
 const comparison=useMemo(()=>data?compareMotion({frames,reference:data.poses,events,duration,view,handedness,stages}):null,[data,frames,events,duration,view,handedness,stages]);
 const aligned=useMemo<ReferenceOverlay|null>(()=>data&&comparison?.alignment?.length&&comparison.fit?{poses:data.poses,fit:comparison.fit,alignment:comparison.alignment,player:data.player,partial:comparison.status!=='available'||comparison.quality==='low',phaseScores:comparison.status==='available'?comparison.phaseScores:undefined}:null,[data,comparison]);
 useEffect(()=>{onOverlayChange(aligned);},[aligned,onOverlayChange]);
 return <>
  <div className="coach-review-title"><h1>Your serve, <em>in focus.</em></h1><span>↗</span></div>
  <div className="coach-score" aria-live="polite"><span className="eyebrow">MOVEMENT SIMILARITY</span>
   {comparison?.status==='available'?<><div className="coach-score-row"><strong>{comparison.score}<small>/100</small></strong><div><b>vs. {data?.player}</b><p>{Math.round(comparison.coverage*100)}% joint coverage · {comparison.quality==='low'?'low-confidence estimate':comparison.quality==='partial'?'partial tracking':'full tracking'}</p></div></div>{comparison.quality==='low'&&<p className="coach-partial-note">{comparison.warnings.join(' ')}</p>}<RegionBreakdown scores={comparison.regionScores} handedness={handedness}/><small>Experimental comparison, not a technique grade.</small></>:<><h2>{error?'Reference unavailable':comparison?'Score unavailable':'Loading comparison…'}</h2><p>{error||comparison?.reason||'Matching your movement to the reference player.'}</p></>}
  </div>
  <div className="coach-reference-picker"><label>Compare with<select aria-label="Reference player" value={player} onChange={e=>{setPlayer(e.target.value);setServe('');}}><option value="djokovic">Novak Djokovic</option><option value="sinner">Jannik Sinner</option></select></label></div>
  {aligned?.partial&&<p className="coach-partial-note">Partial overlay · uncertain portions excluded.</p>}
  {children}
  <details className="coach-reference-details"><summary>Reference & comparison details</summary>
   <label className="field">Serve type<select value={type} onChange={e=>{setType(e.target.value);setServe('');}}><option value="1">First serve</option><option value="2">Second serve</option></select></label>
   {data&&<><label className="field">Individual reference serve<select value={data.selected} onChange={e=>setServe(e.target.value)}>{data.serves.map((r,i)=><option key={r.id} value={r.id}>{i+1}. vs {r.opponent}</option>)}</select></label><p>Estimated professional body poses, aligned to your pace and hip position. The overlay is a skeleton, not the original broadcast video.</p><p>{data.source} · {data.license}</p></>}
   {comparison?.status==='available'&&<><p>This measures similarity, not technique quality. Hidden joints are excluded.</p><dl>{Object.entries(comparison.regionCoverage).map(([name,coverage])=><div key={name}><dt>{({hittingArm:'Hitting arm',tossingArm:'Tossing arm',legs:'Legs',torso:'Torso'} as Record<string,string>)[name]}</dt><dd>{Math.round(coverage*100)}% tracked</dd></div>)}</dl>{comparison.excludedMeasurements.map(note=><p key={note}>{note}</p>)}</>}
  </details>
 </>;
}
