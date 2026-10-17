const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path').join(__dirname,'../visualization/djokovic-88-serves.fragment.html');
const html=fs.readFileSync(path,'utf8');const data=html.match(/id="djoker-data">([\s\S]*?)<\/script>/)[1];
const current=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
function harness(code){
 const nodes=new Map(),queue=new Map(),listeners={},handlers=[];let next=1,draws=0;
 function el(){return {value:'',textContent:'',clientWidth:360,style:{},parentElement:{clientWidth:360},appendChild(){},getBoundingClientRect(){return {left:0,top:0,width:360,height:200,right:360}},getAttribute(){return null}};}
 const root=el();root.querySelector=s=>{if(!nodes.has(s))nodes.set(s,el());return nodes.get(s);};
 root.querySelector('#djoker-data').textContent=data;root.querySelector('#djoker-group').value='All';root.querySelector('#djoker-align').value='phase';
 class Selection{constructor(node=el()){this.n=node}append(){return new Selection()}attr(k,v){if(typeof v==='number')assert.ok(Number.isFinite(v),'Non-finite SVG attribute');if(k==='d'){draws++;assert.ok(!String(v).includes('NaN'));}return this}selectAll(){return this}remove(){return this}call(f){f(this);return this}text(){return this}nodes(){return []}filter(){return this}node(){return this.n}on(name,fn){handlers.push({name,fn});return this}}
 function scale(){let dom=[0,1],ran=[0,1];const s=x=>ran[0]+(x-dom[0])/(dom[1]-dom[0])*(ran[1]-ran[0]);s.domain=v=>(dom=v,s);s.range=v=>(ran=v,s);s.invert=y=>dom[0]+(y-ran[0])/(ran[1]-ran[0])*(dom[1]-dom[0]);return s;}
 function axis(){const f=()=>{};for(const n of ['tickValues','tickSizeOuter','ticks'])f[n]=()=>f;return f;}
 function generator(){const accessors={};const f=xs=>{for(const x of xs)for(const a of Object.values(accessors))assert.ok(Number.isFinite(a(x)),'Non-finite path');return 'M0,0'};for(const k of ['x','y','y0','y1'])f[k]=a=>(accessors[k]=a,f);return f;}
 const context={document:{getElementById:()=>root,createElement:el},window:{openai:{setWidgetState:()=>Promise.resolve()},addEventListener:(n,f)=>listeners[n]=f},
 d3:{select:n=>new Selection(n),extent:x=>[Math.min(...x),Math.max(...x)],scaleLinear:scale,axisBottom:axis,axisLeft:axis,line:generator,area:generator,range:n=>Array.from({length:n},(_,i)=>i),pointer:e=>[e.x,0]},
 performance:{now:()=>100},requestAnimationFrame:f=>{const id=next++;queue.set(id,f);return id},cancelAnimationFrame:id=>queue.delete(id),ResizeObserver:class{observe(){}},console};
 vm.runInNewContext(code,context);
 return {nodes,listeners,handlers,queue,draws:()=>draws,frame(now){const first=queue.entries().next().value;assert.ok(first,'Expected scheduled frame');queue.delete(first[0]);first[1](now)}};
}
// The old implementation mixes clocks and allows a negative interpolation index.
const old=fs.readFileSync(require('node:path').join(__dirname,'fixtures/original-playback.js'),'utf8');
const broken=harness(old);broken.nodes.get('#djoker-play').onclick();assert.throws(()=>broken.frame(99),/Cannot read properties of undefined/);console.log('Reproduced original undefined-index crash with first frame earlier than performance.now().');
const h=harness(current),node=id=>h.nodes.get('#djoker-'+id);
assert.ok(h.draws()>=16);node('play').onclick();h.frame(99);assert.equal(node('progress').textContent,'0%');h.frame(179);assert.equal(node('progress').textContent,'1%');h.frame(150);assert.equal(node('progress').textContent,'1%');
node('play').onclick();assert.equal(h.queue.size,0);node('play').onclick();node('play').onclick();node('play').onclick();assert.equal(h.queue.size,1);h.frame(200);h.frame(8200);assert.equal(node('progress').textContent,'100%');assert.equal(h.queue.size,0);
for(const group of ['All','First serves','Second serves'])for(const alignment of ['phase','progress']){node('group').value=group;node('group').onchange();node('align').value=alignment;node('align').onchange();for(const progress of ['0','37.25','100','-1','101','NaN']){node('scrub').value=progress;node('scrub').oninput();assert.ok(Number.isFinite(Number(node('progress').textContent.replace('%',''))));}}
node('align').value='phase';node('align').onchange();node('play').onclick();h.frame(undefined);h.frame(undefined);node('scrub').value='50';node('scrub').oninput();assert.equal(h.queue.size,0);
h.listeners['openai:set_globals']({detail:{globals:{widgetState:{privateContent:{group:'All',alignment:'phase',progress:Infinity}}}}});assert.equal(node('progress').textContent,'0%');
for(const event of h.handlers.slice(0,3))if(event.name==='pointermove'||event.name==='click')event.fn.call({}, {x:99,clientX:99,clientY:50});
console.log('PASS: initial render; frame-clock regression; pause/replay; no duplicate loops; all groups/alignments; scrubbing boundaries; missing timestamps; restored state; chart pointer handlers.');
