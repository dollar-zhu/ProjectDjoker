import json, os, sys, math, subprocess, shutil
import cv2, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
run=sys.argv[1]; play_fps=float(sys.argv[2]) if len(sys.argv)>2 else 6
d=json.load(open(f"{run}/keypoints.json")); fps=d["fps"]; t0=d["t0"]
files=sorted(os.listdir(f"{run}/work/frames"))
BONES=[(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(15,17),(15,19),(15,21),(16,18),(16,20),(16,22),(0,11),(0,12)]
COL={"R":(60,60,255),"L":(255,160,40),"C":(80,230,80)}
def side(a,b): return "C" if (a in(0,23,24) and b in (0,23,24,11,12)) or (a,b)==(11,12) else ("L" if a in (11,13,15,17,19,21) else "R")
def ang(a,b,c):
    v1,v2=np.array(a[:2])-np.array(b[:2]),np.array(c[:2])-np.array(b[:2])
    return math.degrees(math.acos(np.clip(v1@v2/(np.linalg.norm(v1)*np.linalg.norm(v2)+1e-9),-1,1)))
out=f"{run}/render"; shutil.rmtree(out,ignore_errors=True); os.makedirs(out)
T,EL,ER,WL,WR,SC=[],[],[],[],[],[]
for f in d["frames"]:
    im=cv2.imread(f"{run}/work/frames/{files[f['i']]}"); t=t0+f["i"]/fps
    L=np.array(f["landmarks"]) if f["landmarks"] else None
    ok = L is not None and f["pose_score"]>0.5
    if ok:
        for a,b in BONES:
            cv2.line(im,tuple(map(int,L[a,:2])),tuple(map(int,L[b,:2])),COL[side(a,b)],5,cv2.LINE_AA)
        for k in (0,11,12,13,14,15,16,23,24): cv2.circle(im,tuple(map(int,L[k,:2])),8,(255,255,255),-1,cv2.LINE_AA)
        T.append(t); EL.append(ang(L[11],L[13],L[15])); ER.append(ang(L[12],L[14],L[16]))
        WL.append(-(L[15,1]-L[23,1])); WR.append(-(L[16,1]-L[24,1])); SC.append(f["pose_score"])
    cv2.putText(im,f"t={t:5.2f}s  NPU pose  score={f['pose_score'] if f['pose_score'] is not None else 0:.2f}",(20,50),cv2.FONT_HERSHEY_SIMPLEX,1.3,(0,255,0) if ok else (0,0,255),3,cv2.LINE_AA)
    cv2.imwrite(f"{out}/r{f['i']:05d}.png",cv2.resize(im,(960,720)))
subprocess.run(f'ffmpeg -v error -y -framerate {play_fps} -i {out}/r%05d.png -c:v libx264 -pix_fmt yuv420p -crf 20 {run}/overlay.mp4',shell=True,check=True)
# serve segment: frames with pose_score>0.5 and a wrist well above its hip
fig,ax=plt.subplots(2,1,figsize=(9,6),sharex=True)
ax[0].plot(T,EL,label="left elbow angle",color="#ff9f28"); ax[0].plot(T,ER,label="right elbow angle",color="#3c3cff"); ax[0].set_ylabel("deg"); ax[0].legend(); ax[0].set_title("Elbow angles from NPU keypoints")
ax[1].plot(T,WL,label="left wrist above hip (px)",color="#ff9f28"); ax[1].plot(T,WR,label="right wrist above hip (px)",color="#3c3cff"); ax[1].axhline(0,color="grey",lw=.5); ax[1].set_xlabel("time (s)"); ax[1].legend()
plt.tight_layout(); plt.savefig(f"{run}/angles.png",dpi=110)
json.dump({"t":T,"el":EL,"er":ER,"wl":WL,"wr":WR,"score":SC},open(f"{run}/series.json","w"))
print("frames drawn:",len(d["frames"]),"with skeleton:",len(T))
