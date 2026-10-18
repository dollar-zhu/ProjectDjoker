'use client';
import type {CSSProperties} from 'react';
import type {Stage} from '@/lib/playback';
import type {PhaseScore} from '@/lib/motion-similarity';
import {reviewWindow,stageLanes} from '@/lib/review-focus';

const PHASE_LABELS:Record<string,string>={preparation:'Preparation','upward swing':'Upward swing','follow-through':'Follow-through'};
export const scoreColor=(score:number|null)=>score===null?'#3a4a3f':`color-mix(in oklab, #a8d977 ${Math.round(Math.max(0,Math.min(1,(score-30)/50))*100)}%, #e8794a)`;

/** Scrubber for the serve itself: stage bands and phase similarity share one time scale with the playhead. */
export function ServeTimeline({stages,phaseScores,duration,time,active,onSeek,onReplay}:{stages:Stage[];phaseScores?:PhaseScore[];duration:number;time:number;active:string;onSeek:(t:number)=>void;onReplay:(s:Stage)=>void}){
 const [from,to]=reviewWindow(stages,duration),span=to-from||1;
 const pct=(t:number)=>Math.max(0,Math.min(100,(t-from)/span*100));
 const lanes=stageLanes(stages.filter(s=>s.status==='estimated')),laneCount=Math.max(1,...lanes.map(l=>l.lane+1));
 const missing=stages.filter(s=>s.status!=='estimated');
 const trimmed=from>0||to<duration;
 return <div className="serve-timeline" style={{'--lanes':laneCount} as CSSProperties}>
  <div className="serve-timeline-body">
   <input className="serve-timeline-scrub" aria-label="Video position" type="range" min={from} max={to} step=".01" value={Math.max(from,Math.min(to,time))} onChange={e=>onSeek(+e.target.value)}/>
   {lanes.length>0&&<div className="serve-timeline-lanes">{lanes.map(({stage:s,lane})=><button key={s.id} className={`serve-stage ${active===s.id?'active':''}`} style={{left:`${pct(s.start!)}%`,width:`${Math.max(pct(s.end!)-pct(s.start!),3)}%`,top:`calc(${lane} * (var(--lane-h) + 4px))`}} onClick={()=>onReplay(s)} title={`${s.label} · ${s.start!.toFixed(2)}–${s.end!.toFixed(2)}s · replay at 0.25×`}><span>{s.label}</span></button>)}</div>}
   {!!phaseScores?.length&&<div className="serve-timeline-phases" aria-label="Similarity by phase">{phaseScores.map(p=><span key={p.phase} style={{left:`${pct(p.start)}%`,width:`${pct(p.end)-pct(p.start)}%`,'--c':scoreColor(p.score)} as CSSProperties} title={`${PHASE_LABELS[p.phase]||p.phase}: ${p.score??'not scored'}`}><b>{p.score??'—'}</b><em>{PHASE_LABELS[p.phase]||p.phase}</em></span>)}</div>}
   {time>=from&&time<=to&&<i className="serve-timeline-head" style={{left:`${pct(time)}%`}}/>}
  </div>
  <div className="serve-timeline-foot">
   <span>{trimmed?`Showing ${from.toFixed(1)}–${to.toFixed(1)}s, the serve itself`:'Whole clip'}{missing.length?` · not identified: ${missing.map(s=>s.label.toLowerCase()).join(', ')}`:''}</span>
   {!!phaseScores?.length&&<span className="serve-timeline-key">less similar <i/> more similar</span>}
  </div>
 </div>;
}
