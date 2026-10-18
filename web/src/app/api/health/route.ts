import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {join} from 'node:path';
import {existsSync} from 'node:fs';
import {samples,samplePath,PYTHON,ROOT} from '@/lib/jobs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET() {
 let connected=false;
 try {const {stdout}=await promisify(execFile)('adb',['-s',process.env.DJOKER_SERIAL||'242692658','get-state'],{timeout:4000});connected=stdout.trim()==='device';}catch{}
 const cpu=existsSync(/* turbopackIgnore: true */ process.env.DJOKER_ONNX||join(ROOT,'demo/ventuno-pose/et/onnx/rtmpose_body2d.onnx')) && existsSync(PYTHON);
 return Response.json({connected:connected&&process.env.DJOKER_BACKEND!=='cpu',cpu,python:existsSync(PYTHON),samples:samples.filter(s=>{try{return existsSync(samplePath(s.id));}catch{return false;}})});
}
