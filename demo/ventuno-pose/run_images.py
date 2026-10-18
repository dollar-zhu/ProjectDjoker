import sys, os, math
import numpy as np, cv2
sys.path.insert(0, "."); import posepipe as P
BONES=[(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(15,17),(15,19),(15,21),(16,18),(16,20),(16,22),(0,11),(0,12)]
paths=sys.argv[1:]; os.makedirs("imgs_out",exist_ok=True)
ims=[cv2.imread(p) for p in paths]; rgb=[cv2.cvtColor(i,cv2.COLOR_BGR2RGB) for i in ims]
lb=[P.letterbox(r,128) for r in rgb]
det=P.run_batch("pose_detector",[(x[0].astype(np.float32)/255)[None] for x in lb],"eval_work","imgdet")
rois=[]
for k,(res,(_,s,l,t)) in enumerate(zip(det,lb)):
    ds=P.decode_detections(res,0.3); print(os.path.basename(paths[k]),"size",ims[k].shape[1],"x",ims[k].shape[0],"| detections:",[round(d[0],2) for d in ds[:3]])
    rois.append(P.roi_from_detection(ds[0],s,l,t) if ds else None)
idx=[k for k,r in enumerate(rois) if r]
crops=[P.crop_roi(rgb[k],rois[k]) for k in idx]
lm=P.run_batch("pose_landmark_detector",[(c[0].astype(np.float32)/255)[None] for c in crops],"eval_work","imglm")
for j,k in enumerate(idx):
    F=P.landmarks_to_frame(lm[j]["landmarks"],crops[j][1]); im=ims[k].copy(); sc=float(lm[j]["scores"][0])
    th=max(2,im.shape[1]//300)
    for a,b in BONES: cv2.line(im,tuple(map(int,F[a,:2])),tuple(map(int,F[b,:2])),(60,60,255) if a in (12,14,16,18,20,22) else ((255,160,40) if a in (11,13,15,17,19,21) else (80,230,80)),th*2,cv2.LINE_AA)
    for q in range(25): cv2.circle(im,tuple(map(int,F[q,:2])),th*2,(255,255,255),-1,cv2.LINE_AA)
    cx,cy,side,rot=rois[k]; box=cv2.boxPoints(((cx,cy),(side,side),math.degrees(rot)+90)); cv2.polylines(im,[box.astype(int)],True,(0,255,255),th)
    cv2.putText(im,f"pose score {sc:.2f}",(20,50),cv2.FONT_HERSHEY_SIMPLEX,1.4,(0,255,0),3,cv2.LINE_AA)
    out=f"imgs_out/{os.path.splitext(os.path.basename(paths[k]))[0]}_pose.png"; cv2.imwrite(out,im); print("wrote",out,"score",round(sc,2))
