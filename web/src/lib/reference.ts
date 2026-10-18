export function phaseAt(time:number,duration:number,events:{id:string;time:number}[]):number|null {
 const load=events.find(e=>e.id==='loading')?.time,reach=events.find(e=>e.id==='reach')?.time;
 if(load===undefined||reach===undefined||![time,duration,load,reach].every(Number.isFinite)||!(0<load&&load<reach&&reach<duration))return null;
 const t=Math.max(0,Math.min(duration,time));
 return t<=load?40*t/load:t<=reach?40+40*(t-load)/(reach-load):80+20*(t-reach)/(duration-reach);
}
// Input is rigidly oriented to the estimated rear view; yaw is an offset from behind.
export function projectPose(pose:number[][],yaw:number):number[][] {
 const a=yaw*Math.PI/180;
 return pose.map(([x,y,z])=>[x*Math.cos(a)+y*Math.sin(a),-z]);
}
export function kneeAngle(a:number[],b:number[],c:number[]):number|null {
 const u=[a[0]-b[0],a[1]-b[1]],v=[c[0]-b[0],c[1]-b[1]];
 const d=Math.hypot(...u)*Math.hypot(...v);
 return d>1e-8?Math.acos(Math.max(-1,Math.min(1,(u[0]*v[0]+u[1]*v[1])/d)))*180/Math.PI:null;
}
