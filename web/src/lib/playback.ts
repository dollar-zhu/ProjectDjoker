export function frameAt<T extends {time:number}>(frames:T[],time:number):T|null {
 if(!frames.length || time>frames[frames.length-1].time+.1)return null;
 let lo=0,hi=frames.length-1;
 while(lo<hi){const m=Math.floor((lo+hi)/2);if(frames[m].time<time)lo=m+1;else hi=m;}
 if(lo>0&&Math.abs(frames[lo-1].time-time)<Math.abs(frames[lo].time-time))lo--;
 return frames[lo];
}

export type Stage={id:string;label:string;status:'estimated'|'unavailable';time:number|null;frame:number|null;start:number|null;end:number|null;detail:string;evidence:{id:string;observation:string;cue:string;measurements:Record<string,number>}[]};
export function stagePlayback(stage:Pick<Stage,'status'|'start'|'end'|'time'>,duration:number):{start:number;end:number;rate:number}|null {
 const {start,end,time}=stage;
 if(stage.status!=='estimated'||start===null||end===null||time===null||![start,end,time,duration].every(Number.isFinite)||start<0||start>time||time>end||end>duration||end<=start)return null;
 return {start,end,rate:.25};
}
