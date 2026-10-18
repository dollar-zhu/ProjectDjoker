"""One local job: prepare playback, or run local pose inference and strict coaching.

Inference uses Ventuno when connected, otherwise ONNX Runtime on the host CPU.
All working paths belong to a UUID job; no shared model directories are modified.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

import cv2
import numpy as np
from review import review
from pose import crop_input,decode

MODEL='/home/arduino/models/et/rtmpose_qnn_fp16_QCS8275.pte'
RUNNER='/home/arduino/git/executorch/build-x86/examples/qualcomm/executor_runner/qnn_executor_runner'
ONNX=Path(os.environ.get('DJOKER_ONNX',Path(__file__).resolve().parents[2]/'demo/ventuno-pose/et/onnx/rtmpose_body2d.onnx'))
ENV='export LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"; '


def command(args,timeout=120):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-2000:])
    return p.stdout+p.stderr


def update(d,**fields):
    job=json.loads((d/'job.json').read_text());job.update(fields);job['updated']=time.time()
    temp=d/'job.tmp';temp.write_text(json.dumps(job,allow_nan=False));temp.replace(d/'job.json')
    return job


def prepare(d):
    p=json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(d/'input')]))
    video=next((s for s in p['streams'] if s['codec_type']=='video'),None)
    if not video: raise ValueError('No video stream was found.')
    duration=float(p['format'].get('duration',video.get('duration',0)))
    if not .5<=duration<=20: raise ValueError('Use one serve between 0.5 and 20 seconds. Trim longer recordings first.')
    if max(video['width'],video['height'])>7680: raise ValueError('Use a video up to 8K resolution.')
    command(['ffmpeg','-v','error','-y','-i',str(d/'input'),'-map','0:v:0','-map','0:a?',
             '-vf',"scale=w='min(1280,iw)':h='min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1,fps=30",
             '-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(d/'video.mp4')])
    p=json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(d/'video.mp4')]))
    v=next(s for s in p['streams'] if s['codec_type']=='video')
    command(['ffmpeg','-v','error','-i',str(d/'video.mp4'),'-frames:v','1','-y',str(d/'poster.jpg')])
    update(d,status='ready',stage='Select the player',meta={'width':v['width'],'height':v['height'],
           'duration':float(p['format']['duration']),'playback_fps':30,'audio':any(s['codec_type']=='audio' for s in p['streams'])})


def recorded_tracking(d,job):
    """Reuse camera observations only for the same player selection and geometry.

    Re-inference on compressed/resampled video can lose the very recovery that
    ended live capture. Completion labels are never evidence: review still
    derives every event from the original confidence-masked joints.
    """
    capture=job.get('capture',{});meta=job['meta']
    if (capture.get('source')!='Ventuno USB webcam'
            or capture.get('tracking_options')!=job['options']
            or capture.get('tracking_image_size')!=[meta['width'],meta['height']]):
        return None
    try:
        frames=json.loads((d/'tracking.json').read_text())
        times=np.asarray([f['time'] for f in frames],float)
        poses=np.asarray([f['xy'] for f in frames],float)
        scores=np.asarray([f['scores'] for f in frames],float)
        if (len(times)<15 or poses.shape!=(len(times),17,2) or scores.shape!=(len(times),17)
                or not all(np.isfinite(a).all() for a in [times,poses,scores])
                or not (np.diff(times)>0).all() or times[0]!=0
                or times[-1]>meta['duration'] or meta['duration']-times[-1]>.2):
            return None
        # The live gate rejects a pose whose hip center leaves its inference
        # area. Preserve that rejection instead of reviving a bystander's pose.
        for i,f in enumerate(frames):
            x1,y1,x2,y2=f['crop']
            x,y=poses[i,11:13].mean(0)/[meta['width'],meta['height']]
            if not (x1<=x<=x2 and y1<=y<=y2): scores[i]=0
        return times,poses,scores
    except (OSError,ValueError,KeyError,TypeError):
        return None


def finish_review(d,job,times,poses,scores,stats):
    o=job['options'];w,h=job['meta']['width'],job['meta']['height']
    update(d,stage='Finding moments and preparing feedback',progress=90)
    tracked_crop=job.get('capture',{}).get('crop_mode')=='recorded_tracking_extent'
    if (d/'dms').exists(): shutil.rmtree(d/'dms')
    result=review(d,times,poses,scores,o['view'],o['handedness'],[w,h],
                  crop_mode='recorded_tracking_extent' if tracked_crop else 'fixed_operator',
                  runtime=stats['backend'])
    recorded=stats.get('pose_source')=='recorded_live_tracking'
    result.update({'frames':[{'time':float(t),'xy':p.tolist(),'scores':s.tolist()} for t,p,s in zip(times,poses,scores)],
        'stats':stats,
        'limitations':[('Original live camera joints and timestamps retained; uncertain joints remain excluded.' if recorded else
                        'Player crop estimated from recorded tracking; inspect the skeleton for cropping or occlusion errors.' if tracked_crop else
                        'Player crop selected manually; inspect the skeleton for wrong-person or occlusion errors.'),
        'Body-movement stages are estimates. Ball release, racket drop, contact and landing are not measured. Missing stages reflect insufficient tracking.',
        'Reference-based corrections and scores are withheld until validated.',
        'All processing ran locally on the Mac CPU.' if 'CPU' in stats['backend'] else 'Mac prepares video and feedback; Ventuno performs pose inference.']})
    temp=d/'result.tmp';temp.write_text(json.dumps(result,allow_nan=False));temp.replace(d/'result.json')
    update(d,status='complete',stage='Review ready',progress=100)


def process(d):
    started=time.monotonic();job=json.loads((d/'job.json').read_text());o=job['options']
    tracked=recorded_tracking(d,job)
    if tracked is not None:
        times,poses,scores=tracked
        finish_review(d,job,times,poses,scores,{
            'frames':len(times),'sample_fps':float(1/np.median(np.diff(times))),
            'mean_inference_ms':None,'processing_seconds':round(time.monotonic()-started,2),
            'backend':job['capture']['tracking_backend'],'pose_source':'recorded_live_tracking'})
        return
    update(d,status='queued',stage='Waiting for processor')
    # Serialize all workers, including workers launched by different Next.js processes.
    with open(d.parent/'ventuno.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        adb=['adb','-s',os.environ.get('DJOKER_SERIAL','242692658')]
        connected=False
        if os.environ.get('DJOKER_BACKEND') != 'cpu':
            try: connected=command(adb+['get-state'],10).strip()=='device'
            except (RuntimeError, OSError, subprocess.TimeoutExpired): pass
        session=None
        if not connected:
            if not ONNX.exists():
                raise RuntimeError('No local pose model available. Set DJOKER_ONNX to the wholebody ONNX model or connect Ventuno.')
            import onnxruntime as ort
            options=ort.SessionOptions();options.intra_op_num_threads=4
            session=ort.InferenceSession(str(ONNX),sess_options=options,providers=['CPUExecutionProvider'])
            if session.get_inputs()[0].shape != [1,3,256,192]:
                raise ValueError('Unexpected ONNX input contract; use the exported wholebody RTMPose model.')
        update(d,status='processing',stage='Preparing player crops',progress=15)
        frames=d/'frames';inputs=d/'inputs';outputs=d/'outputs'
        for folder in [frames,inputs,outputs]:
            if folder.exists(): shutil.rmtree(folder)
        frames.mkdir();inputs.mkdir()
        command(['ffmpeg','-v','error','-i',str(d/'video.mp4'),'-vf','fps=20',str(frames/'%05d.jpg')])
        files=sorted(frames.glob('*.jpg'));w,h=job['meta']['width'],job['meta']['height']
        poses=[];scores=[];latencies=[]
        if session:
            update(d,stage='Running RTMPose on Mac CPU',progress=30)
            for i,f in enumerate(files):
                blob,matrix=crop_input(cv2.imread(str(f)),o['crop'])
                tick=time.monotonic()
                px,py=session.run(None,{session.get_inputs()[0].name:blob})
                latencies.append((time.monotonic()-tick)*1000)
                if not (np.isfinite(px).all() and np.isfinite(py).all()):
                    raise ValueError('Pose output contains nonfinite values.')
                xy,score=decode(px,py,matrix);poses.append(xy);scores.append(score)
                if i%10==0: update(d,progress=30+int(55*(i+1)/len(files)))
            (d/'runner.log').write_text(f'ONNX Runtime CPUExecutionProvider\nFrames: {len(files)}\nMean inference: {np.mean(latencies):.2f} ms\n')
        else:
            for i,f in enumerate(files):
                blob,matrix=crop_input(cv2.imread(str(f)),o['crop'])
                blob.astype('<f4').tofile(inputs/f'{i:05d}.raw')
            board='/home/arduino/djoker-web/'+d.name
            (inputs/'list.txt').write_text(''.join(f'{board}/inputs/{i:05d}.raw\n' for i in range(len(files))))
            command(adb+['shell',f'mkdir -p {board}/out'])
            update(d,stage='Sending crops to Ventuno',progress=30)
            command(adb+['push',str(inputs),board+'/'])
            update(d,stage='Running RTMPose on Ventuno',progress=50)
            log=command(adb+['shell',ENV+f'{RUNNER} --model_path {MODEL} --input_list_path {board}/inputs/list.txt --output_folder_path {board}/out --iteration 1 --warm_up 2'])
            (d/'runner.log').write_text(log)
            update(d,stage='Reading tracked joints',progress=70)
            command(adb+['pull',board+'/out',str(outputs)])
            # Delete only this job's generated tensors after a successful transfer.
            command(adb+['shell',f'rm -rf {board}'])
            for i in range(len(files)):
                px=np.fromfile(outputs/f'output_{i}_0.raw','<f4').reshape(133,384)
                py=np.fromfile(outputs/f'output_{i}_1.raw','<f4').reshape(133,512)
                if not (np.isfinite(px).all() and np.isfinite(py).all()): raise ValueError('Pose output contains nonfinite values.')
                xy,score=decode(px,py,matrix);poses.append(xy);scores.append(score)
            latencies=[float(x) for x in re.findall(r'1 inference took ([\d.]+) ms',log)]
    poses=np.asarray(poses);scores=np.asarray(scores);times=np.arange(len(poses))/20
    for folder in [frames,inputs,outputs]:
        if folder.exists(): shutil.rmtree(folder)
    finish_review(d,job,times,poses,scores,{
        'frames':len(poses),'sample_fps':20,'mean_inference_ms':float(np.mean(latencies)) if latencies else None,
        'processing_seconds':round(time.monotonic()-started,2),'backend':'Mac CPU · ONNX Runtime' if session else 'Ventuno · ExecuTorch QNN FP16'})


if __name__=='__main__':
    mode,d=sys.argv[1],Path(sys.argv[2]).resolve()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',d.name): raise ValueError('Invalid job id')
    try:
        if mode=='prepare': prepare(d)
        elif mode=='process': process(d)
        else: raise ValueError('Unknown operation')
    except Exception as exc:
        traceback.print_exc()
        update(d,status='failed',stage='Processing stopped',error=str(exc)[-2000:])
        sys.exit(1)
