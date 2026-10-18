export type Analysis={focus_id:string|null;stage_id?:string|null;title:string;observation:string;rationale:string;cue:string;drill:string;success_check:string;limitation:string;source:string;model_status:string;note?:string;evidence_times:number[]};

// Share only pending work, including React's development effect remount.
// A deliberate retry or a later visit can request fresh analysis.
const pending=new Map<string,Promise<Analysis>>();
export function loadCoaching(jobId:string,fetcher:typeof fetch=fetch):Promise<Analysis>{
 const existing=pending.get(jobId);if(existing)return existing;
 const result=(async()=>{
  const response=await fetcher('/api/commentary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId}),signal:AbortSignal.timeout(145000)});
  const plan=await response.json();
  if(!response.ok)throw Error(plan.error||'Coaching unavailable');
  return plan as Analysis;
 })().finally(()=>pending.delete(jobId));
 pending.set(jobId,result);return result;
}
