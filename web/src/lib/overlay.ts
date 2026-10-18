import {projectPose,kneeAngle} from './reference';
import type {MotionAlignment,PhaseScore} from './motion-similarity';
export type PoseFrame={time:number;xy:number[][];scores:number[]};
export type Fit={yaw:0;mirror:false;scale:number;error:number};
export type ReferenceOverlay={poses:number[][][];fit:Fit;player:string;alignment:MotionAlignment;partial:boolean;phaseScores?:PhaseScore[]};
export const REFERENCE_BONES=[[0,1],[1,2],[2,3],[0,4],[4,5],[5,6],[0,7],[7,8],[8,9],[9,10],[8,11],[11,12],[12,13],[8,14],[14,15],[15,16]];
const midpoint=(a:number[],b:number[])=>[(a[0]+b[0])/2,(a[1]+b[1])/2];
const distance=(a:number[],b:number[])=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const valid=(u:PoseFrame,ids:number[])=>ids.every(i=>u.scores[i]>=.5&&u.xy[i]?.every(Number.isFinite));
export function fitReference(reference:number[][],user:PoseFrame):Fit|null {
 if(!valid(user,[5,6,11,12]))return null;
 const center=midpoint(user.xy[11],user.xy[12]),torso=distance(midpoint(user.xy[5],user.xy[6]),center);
 if(torso<10)return null;
 // Reference poses are already oriented from behind. Fit only size and position.
 const p=projectPose(reference,0),root=midpoint(p[4],p[1]);
 const size=distance(midpoint(p[11],p[14]),root);if(size<.05)return null;
 const scale=torso/size;
 const error=[[5,11],[6,14],[11,4],[12,1]].reduce((sum,[c,h])=>sum+((p[h][0]-root[0])*scale-(user.xy[c][0]-center[0]))**2+((p[h][1]-root[1])*scale-(user.xy[c][1]-center[1]))**2,0)/torso**2;
 return {yaw:0,mirror:false,scale,error};
}
export function alignedReference(reference:number[][],user:PoseFrame,fit:Fit):number[][]|null {
 if(!valid(user,[11,12]))return null;
 const p=projectPose(reference,0);
 const root=midpoint(p[4],p[1]),center=midpoint(user.xy[11],user.xy[12]);
 return p.map(([x,y])=>[(x-root[0])*fit.scale+center[0],(y-root[1])*fit.scale+center[1]]);
}
export type Evidence={player:string;time:number;userLeft:number;userRight:number;referenceLeft:number;referenceRight:number};
export function loadingEvidence(user:PoseFrame,reference2d:number[][],player:string,time:number):Evidence|null {
 if(!valid(user,[11,12,13,14,15,16]))return null;
 const values=[kneeAngle(user.xy[11],user.xy[13],user.xy[15]),kneeAngle(user.xy[12],user.xy[14],user.xy[16]),kneeAngle(reference2d[4],reference2d[5],reference2d[6]),kneeAngle(reference2d[1],reference2d[2],reference2d[3])];
 if(values.some(v=>v===null||!Number.isFinite(v)))return null;
 return{player,time,userLeft:values[0]!,userRight:values[1]!,referenceLeft:values[2]!,referenceRight:values[3]!};
}
