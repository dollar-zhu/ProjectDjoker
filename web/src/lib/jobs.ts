import {readFile,writeFile,rename,mkdir,readdir} from 'node:fs/promises';
import {existsSync,openSync,closeSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {validId} from './contracts';

export const ROOT=resolve(process.cwd(),'..');
export const DATA=process.env.DJOKER_DATA_DIR || join(ROOT,'local','web-jobs');
const testedPython=join(ROOT,'demo/ventuno-pose/et/.venv-et/bin/python');
export const PYTHON=process.env.DJOKER_PYTHON || (existsSync(testedPython)?testedPython:join(ROOT,'.venv/bin/python'));
export const WORKER=join(ROOT,'web/processor/worker.py');
export function jobDir(id:string) {if(!validId(id))throw Error('Invalid job id');return join(DATA,id);}
export async function loadJob(id:string) {return JSON.parse(await readFile(join(jobDir(id),'job.json'),'utf8'));}
export async function saveJob(id:string,job:unknown) {
 const dir=jobDir(id);await mkdir(dir,{recursive:true});
 const tmp=join(dir,'job.node.tmp');await writeFile(tmp,JSON.stringify(job));await rename(tmp,join(dir,'job.json'));
}
export async function prepare(id:string) {await promisify(execFile)(PYTHON,[WORKER,'prepare',jobDir(id)],{timeout:120000,maxBuffer:1024*1024});}
export function launch(id:string) {
 const fd=openSync(join(jobDir(id),'worker.log'),'a');
 const child=spawn(/* turbopackIgnore: true */ PYTHON,[WORKER,'process',jobDir(id)],{detached:true,stdio:['ignore',fd,fd]});
 closeSync(fd);
 child.on('error',async()=>{const j=await loadJob(id);await saveJob(id,{...j,status:'failed',error:'Could not start the Python processor. Check DJOKER_PYTHON.'});});
 child.on('exit',async code=>{
  if(code===0)return;
  const j=await loadJob(id);
  if(['queued','processing'].includes(j.status))await saveJob(id,{...j,status:'failed',stage:'Processor stopped',error:'The processor exited unexpectedly. Check worker.log and the Python dependencies, then retry.'});
 });
 child.unref();
}
export async function listJobs() {
 await mkdir(DATA,{recursive:true});
 const jobs=await Promise.all((await readdir(/* turbopackIgnore: true */ DATA)).filter(validId).map(id=>loadJob(id).catch(()=>null)));
 return jobs.filter(Boolean).sort((a,b)=>b.created-a.created).slice(0,12);
}
export const samples=[
 {id:'a001',name:'Bremen',label:'Recreational · rear view',file:'a001_bremen.mp4',crop:[.492,.225,.808,.975],view:'rear'},
 {id:'p001',name:'Federer',label:'Pro reference · slow motion',file:'p001_federer.mp4',crop:[.505,.36,.775,1],view:'rear'},
 {id:'a004',name:'Sara',label:'Advanced · rear view',file:'a004_sara.mp4',crop:[.38234,.25,.67766,.95],view:'rear'},
 {id:'a002',name:'Stephen',label:'Front view · limitation case',file:'a002_stephen.mp4',crop:[0,0,1,1],view:'front'},
];
export function samplePath(id:string) {
 const s=samples.find(s=>s.id===id);if(!s)throw Error('Unknown sample');
 const path=join(ROOT,'benchmark/manual/samples',s.file);if(!existsSync(path))throw Error('Sample video is not available on this machine. Upload your own clip.');return path;
}
