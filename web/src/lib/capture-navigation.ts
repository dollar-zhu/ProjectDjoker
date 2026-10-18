export type CaptureSnapshot={state:string;jobId?:string};
export function reviewFromCapture(previous:CaptureSnapshot|null,current:CaptureSnapshot):string|null{if(!previous||!current.jobId)return null;
 if(current.jobId!==previous.jobId||(previous.state==='processing'&&current.state!=='processing'))return current.jobId;
 return null;}
