
(()=>{
const root=document.getElementById('djoker-population'),D=JSON.parse(root.querySelector('#djoker-data').textContent);
const group=root.querySelector('#djoker-group'),align=root.querySelector('#djoker-align'),scrub=root.querySelector('#djoker-scrub'),play=root.querySelector('#djoker-play'),tooltip=root.querySelector('.tooltip');
let t=0,playing=false,last=0,plots=[],meanVisible=true;
const saved=window.openai?.widgetState?.privateContent;
if(saved){if(D.groups[saved.group])group.value=saved.group;if(['phase','progress'].includes(saved.alignment))align.value=saved.alignment;t=Math.max(0,Math.min(100,Number(saved.progress)||0));}
const persist=()=>window.openai?.setWidgetState?.({modelContent:{serves:group.value,n:D.groups[group.value].n,alignment:align.value},privateContent:{group:group.value,alignment:align.value,progress:t}})?.catch(()=>{});
const interp=(v,x,j)=>{const i=Math.floor(x),f=x-i;const a=j===undefined?v[i]:v[i][j],b=j===undefined?v[Math.min(100,i+1)]:v[Math.min(100,i+1)][j];return a+(b-a)*f;};
D.joint_names.forEach((name,j)=>{const div=document.createElement('div');div.className='plot';const h=document.createElement('h3');h.textContent=name;div.appendChild(h);const svg=d3.select(div).append('svg').attr('class','plot-svg').attr('role','img').attr('aria-label',name+' mean angle and tenth-to-ninetieth percentile band');root.querySelector('.plots').appendChild(div);plots.push({div,svg,j,name});});
function drawCharts(){
const g=D.groups[group.value],stats=g[align.value];root.querySelector('#djoker-count').textContent=`${g.n} serves · ${group.value==='All'?'75 first / 13 second':group.value.toLowerCase()} · provisional geometry`;
plots.forEach(p=>{const W=p.div.clientWidth,H=230,M={l:64,r:18,t:16,b:52},svg=p.svg;svg.attr('viewBox',`0 0 ${W} ${H}`).selectAll('*').remove();
const extent=d3.extent([...stats.p10.map(v=>v[p.j]),...stats.p90.map(v=>v[p.j]),...stats.mean.map(v=>v[p.j])]),pad=Math.max(3,(extent[1]-extent[0])*.08);
const x=d3.scaleLinear().domain([0,100]).range([M.l+3,W-M.r-3]),y=d3.scaleLinear().domain([Math.max(0,extent[0]-pad),Math.min(180,extent[1]+pad)]).range([H-M.b-3,M.t+3]);p.x=x;p.y=y;p.stats=stats;
svg.append('rect').attr('data-chart-frame','').attr('x',M.l).attr('y',M.t).attr('width',W-M.l-M.r).attr('height',H-M.b-M.t).attr('fill','none').attr('stroke','var(--border)');
svg.append('g').attr('transform',`translate(0,${H-M.b})`).call(d3.axisBottom(x).tickValues(W<400?[0,40,80,100]:[0,20,40,60,80,100]).tickSizeOuter(0));
svg.append('g').attr('transform',`translate(${M.l},0)`).call(d3.axisLeft(y).ticks(4).tickSizeOuter(0));
svg.append('text').attr('class','axis-title').attr('data-axis','x').attr('x',(M.l+W-M.r)/2).attr('y',H-8).attr('text-anchor','middle').text(align.value==='phase'?'Estimated-phase progress (%)':'Original clip progress (%)');
svg.append('text').attr('class','axis-title').attr('data-axis','y').attr('transform','rotate(-90)').attr('x',-(M.t+H-M.b)/2).attr('y',16).attr('text-anchor','middle').text('Angle (°)');
if(align.value==='phase')[40,80].forEach(a=>svg.append('line').attr('x1',x(a)).attr('x2',x(a)).attr('y1',M.t).attr('y2',H-M.b).attr('stroke','var(--border)'));
const xs=d3.range(101);svg.append('path').attr('class','band').attr('d',d3.area().x(i=>x(i)).y0(i=>y(stats.p10[i][p.j])).y1(i=>y(stats.p90[i][p.j]))(xs));svg.append('path').attr('class','mean').attr('d',d3.line().x(i=>x(i)).y(i=>y(stats.mean[i][p.j]))(xs));
p.cursor=svg.append('line').attr('class','cursor').attr('y1',M.t).attr('y2',H-M.b);p.dot=svg.append('circle').attr('r',3.5).attr('fill','var(--viz-series-1)');
p.hover=svg.append('line').attr('data-chart-hover-guide','').attr('stroke','var(--foreground)').attr('y1',M.t).attr('y2',H-M.b).attr('visibility','hidden');p.hoverDot=svg.append('circle').attr('data-chart-hover-marker','').attr('r',4).attr('fill','var(--viz-series-1)').attr('visibility','hidden');
svg.append('rect').attr('data-chart-hit','').attr('data-chart-hover-overlay','cross-series').attr('x',M.l).attr('y',M.t).attr('width',W-M.l-M.r).attr('height',H-M.b-M.t).attr('fill','transparent').on('pointermove',function(e){const tx=Math.max(0,Math.min(100,x.invert(d3.pointer(e,this)[0]))),v=interp(stats.mean,tx,p.j);p.hover.attr('x1',x(tx)).attr('x2',x(tx)).attr('visibility','visible');p.hoverDot.attr('cx',x(tx)).attr('cy',y(v)).attr('visibility','visible');tooltip.hidden=false;tooltip.textContent=`${p.name} · ${tx.toFixed(1)}% · mean ${v.toFixed(1)}° · 10–90% ${interp(stats.p10,tx,p.j).toFixed(1)}–${interp(stats.p90,tx,p.j).toFixed(1)}°`;const r=root.getBoundingClientRect();tooltip.style.left=Math.max(0,Math.min(root.clientWidth-tooltip.offsetWidth,e.clientX-r.left+12))+'px';tooltip.style.top=(e.clientY-r.top+15)+'px';}).on('pointerleave',()=>{tooltip.hidden=true;p.hover.attr('visibility','hidden');p.hoverDot.attr('visibility','hidden');}).on('click',function(e){playing=false;play.textContent='Play serve';t=Math.max(0,Math.min(100,x.invert(d3.pointer(e,this)[0])));update();persist();});
// Measure labels after layout; preserve the axes, prune optional ticks if adjacent labels collide.
const ticks=svg.selectAll('.tick text').nodes();let boxes=ticks.map(n=>n.getBoundingClientRect());if(boxes.some((b,i)=>i>0&&b.width&&b.top===boxes[i-1].top&&b.left<boxes[i-1].right+4))svg.selectAll('g').filter(function(){return this.getAttribute('transform')===`translate(0,${H-M.b})`;}).call(d3.axisBottom(x).tickValues([0,40,80,100]).tickSizeOuter(0));
});update();}
function drawPose(){
const svg=d3.select(root.querySelector('.pose-svg')),W=svg.node().parentElement.clientWidth,H=280;svg.attr('viewBox',`0 0 ${W} ${H}`).selectAll('*').remove();
const g=D.groups[group.value],data=g.pose2d,idx=Math.round(t),ex=D.pose_extent,pad=15,scale=Math.min((W-pad*2)/(ex[1]-ex[0]),(H-pad*2)/(ex[3]-ex[2]));
const px=x=>W/2+(x-(ex[0]+ex[1])/2)*scale,py=y=>H/2+(y-(ex[2]+ex[3])/2)*scale;
if(align.value==='progress'){svg.append('text').attr('x',W/2).attr('y',H/2).attr('text-anchor','middle').text('Pose playback uses estimated-phase alignment');return;}
for(let j=0;j<17;j++){const a=data.p10[idx][j],b=data.p90[idx][j];svg.append('ellipse').attr('class','pose-band').attr('cx',px((a[0]+b[0])/2)).attr('cy',py((a[1]+b[1])/2)).attr('rx',Math.max(1,(b[0]-a[0])*scale/2)).attr('ry',Math.max(1,(b[1]-a[1])*scale/2));}
D.edges.forEach(([a,b])=>{const u=data.mean[idx][a],v=data.mean[idx][b];svg.append('line').attr('class','pose-line').attr('x1',px(u[0])).attr('y1',py(u[1])).attr('x2',px(v[0])).attr('y2',py(v[1]));});
data.mean[idx].forEach(a=>svg.append('circle').attr('class','pose-dot').attr('cx',px(a[0])).attr('cy',py(a[1])).attr('r',2.8));}
function update(){scrub.value=t;root.querySelector('#djoker-progress').textContent=t.toFixed(0)+'%';root.querySelector('#djoker-phase').textContent=align.value==='phase'?(t<40?'Loading':t<80?'Drive & upward swing':'Follow-through')+' · estimated':'Original clip progress · phases unaligned';plots.forEach(p=>{if(p.cursor){p.cursor.attr('x1',p.x(t)).attr('x2',p.x(t));p.dot.attr('cx',p.x(t)).attr('cy',p.y(interp(p.stats.mean,t,p.j)));}});drawPose();}
play.onclick=()=>{playing=!playing;if(playing&&t>=100)t=0;play.textContent=playing?'Pause':'Play serve';last=performance.now();if(playing)requestAnimationFrame(tick);root.querySelector('#djoker-status').textContent=playing?'Playing serve':'Playback paused';};
function tick(now){if(!playing)return;t=Math.min(100,t+(now-last)/80);last=now;update();if(t>=100){playing=false;play.textContent='Replay serve';persist();}else requestAnimationFrame(tick);}
scrub.oninput=()=>{playing=false;play.textContent='Play serve';t=Number(scrub.value);update();};scrub.onchange=persist;
group.onchange=()=>{drawCharts();persist();};align.onchange=()=>{drawCharts();persist();};
window.addEventListener('openai:set_globals',e=>{const s=e.detail?.globals?.widgetState?.privateContent;if(!s)return;if(D.groups[s.group])group.value=s.group;if(['phase','progress'].includes(s.alignment))align.value=s.alignment;t=Math.max(0,Math.min(100,Number(s.progress)||0));drawCharts();});
new ResizeObserver(()=>drawCharts()).observe(root);drawCharts();
})();
