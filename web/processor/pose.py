"""Pre/postprocessing for the existing wholebody ExecuTorch QNN model.

This model accepts BGR float32 0..255 NCHW and normalizes internally. Do not
substitute the separately normalized body7 ONNX model without changing this contract.
"""
import cv2
import numpy as np

def crop_input(image,box):
    h,w=image.shape[:2]
    x1,y1,x2,y2=np.asarray(box)*[w,h,w,h]
    height=max(y2-y1,(x2-x1)*256/192)
    scale=height/256
    matrix=np.array([[scale,0,(x1+x2)/2-scale*96],
                     [0,scale,(y1+y2)/2-scale*128]],np.float32)
    crop=cv2.warpAffine(image,matrix,(192,256),flags=cv2.WARP_INVERSE_MAP|cv2.INTER_LINEAR,borderValue=0)
    return crop.astype(np.float32).transpose(2,0,1)[None],matrix

def decode(px,py,matrix):
    px=px.reshape(133,384)[:17];py=py.reshape(133,512)[:17]
    xy=np.stack([px.argmax(1)/2,py.argmax(1)/2,np.ones(17)],1)@matrix.T
    return xy,np.minimum(px.max(1),py.max(1))
