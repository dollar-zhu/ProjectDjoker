export type Options = {crop: number[]; view: 'rear'|'side'|'front'|'unknown'; handedness: 'right'|'left'|'unknown'};
export function parseOptions(input: unknown): Options {
  const value = input as Options;
  if (!value || !['rear','side','front','unknown'].includes(value.view) || !['right','left','unknown'].includes(value.handedness)) throw Error('Choose the camera view and hitting hand.');
  const c = value.crop;
  if (!Array.isArray(c) || c.length!==4 || !c.every(v=>typeof v==='number' && Number.isFinite(v) && v>=0 && v<=1) || c[2]-c[0]<.08 || c[3]-c[1]<.15) throw Error('Draw a larger box around the player, including the raised arms and feet.');
  return {crop:c,view:value.view,handedness:value.handedness};
}
export function validId(id:string) { return /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id); }
export function parseRange(header:string,size:number): [number,number] {
  const m=/^bytes=(\d*)-(\d*)$/.exec(header);
  if (!m || (!m[1]&&!m[2])) throw Error('Invalid range');
  const start=m[1]?Number(m[1]):Math.max(0,size-Number(m[2]));
  const end=m[1]?(m[2]?Math.min(size-1,Number(m[2])):size-1):size-1;
  if (!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start>end||start>=size) throw Error('Unsatisfiable range');
  return [start,end];
}
