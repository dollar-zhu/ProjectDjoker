from pathlib import Path
import json,os
import numpy as np
os.environ['MPLCONFIGDIR']=str(Path('.mplconfig').resolve())
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
out=Path('.');d=json.loads(Path('visual_data.json').read_text());g=d['groups']['All'];stats=g['phase'];mean=np.array(stats['mean']);lo=np.array(stats['p10']);hi=np.array(stats['p90']);pose=np.array(g['pose']);edges=d['edges']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(14,9),facecolor='#fafaf7');gs=fig.add_gridspec(4,3,width_ratios=[1.15,1,1],left=.035,right=.98,top=.88,bottom=.08,hspace=.52,wspace=.33)
axp=fig.add_subplot(gs[:3,0],projection='3d');axp.set_facecolor('#fafaf7');axp.set(xlim=(-1.3,1.3),ylim=(-1.3,1.3),zlim=(-1.9,2.9));axp.set_box_aspect((2.6,2.6,4.8));axp.view_init(elev=10,azim=-65);axp.set_axis_off()
lines=[axp.plot([],[],[],color='#16695e',lw=3,marker='o',markersize=3)[0] for _ in edges]
label=fig.text(.06,.28,'',fontsize=12,color='#16695e');fig.text(.06,.16,'Mean normalized skeleton\nH36M mapping provisional\nBall contact is not observed',fontsize=10,linespacing=1.7,color='#51575a')
fig.suptitle('Djokovic · 88-serve reference distribution',fontsize=21,x=.04,ha='left',y=.97)
fig.text(.04,.92,'75 first serves + 13 second serves  |  solid line: mean angle  |  shaded band: middle 80% of serves',fontsize=11)
cursors=[];dots=[]
for j,name in enumerate(d['joint_names']):
 ax=fig.add_subplot(gs[j//2,j%2+1]);ax.set_facecolor('#fafaf7');ax.fill_between(range(101),lo[:,j],hi[:,j],color='#43a190',alpha=.22,linewidth=0);ax.plot(mean[:,j],color='#16695e',lw=1.7)
 for x in [40,80]:ax.axvline(x,color='#cdd2cf',lw=.8)
 ax.set_title(name,loc='left',fontsize=11,pad=5);ax.set_xlim(0,100);ax.set_ylabel('Degrees',fontsize=9);ax.set_xticks([0,40,80,100]);ax.tick_params(labelsize=8);ax.grid(axis='y',alpha=.15)
 cursors.append(ax.axvline(0,color='#595f5c',lw=1));dots.append(ax.plot([0],[mean[0,j]],'o',color='#16695e',markersize=4)[0])
fig.text(.38,.025,'Estimated-phase progress (%)  ·  40 = deepest knee bend  ·  80 = highest right wrist',fontsize=10)
frames=[]
for t in range(0,101,2):
 for line,(a,b) in zip(lines,edges):line.set_data_3d(pose[t,[a,b],0],pose[t,[a,b],1],pose[t,[a,b],2])
 for j,(cur,dot) in enumerate(zip(cursors,dots)):cur.set_xdata([t,t]);dot.set_data([t],[mean[t,j]])
 phase='Loading' if t<40 else 'Drive & upward swing' if t<80 else 'Follow-through'
 label.set_text(f'{phase} · estimated\n{t}% of aligned sequence')
 fig.canvas.draw();frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3].copy()).convert('P',palette=Image.Palette.ADAPTIVE,colors=128))
frames[0].save(out/'djokovic-88-serves.gif',save_all=True,append_images=frames[1:],duration=150,loop=0,optimize=False)
frames[30].convert('RGB').save(out/'preview.png');plt.close(fig)
print(out/'djokovic-88-serves.gif')
