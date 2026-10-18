export function frameAt<T extends {time:number}>(frames:T[],time:number):T|null {
 if(!frames.length || time>frames[frames.length-1].time+.1)return null;
 let lo=0,hi=frames.length-1;
 while(lo<hi){const m=Math.floor((lo+hi)/2);if(frames[m].time<time)lo=m+1;else hi=m;}
 if(lo>0&&Math.abs(frames[lo-1].time-time)<Math.abs(frames[lo].time-time))lo--;
 return frames[lo];
}
