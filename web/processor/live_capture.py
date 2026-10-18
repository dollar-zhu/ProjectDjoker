"""Stream the board webcam over USB; track on host CPU and review on Ventuno.

No service or packages are installed on the board. The adb-owned ffmpeg process
closes with the pipe. Only a completed estimated serve enters the review queue.
"""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import uuid

import cv2
import numpy as np
from capture import ServeCapture, ReadyServeCapture, ManualCapture, PlayerCrop, pose_signal, ready_pose
from pose import crop_input, decode
from worker import ONNX, prepare, process, update

BONES = [(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)]


class TimedRecording:
    """Resample observed capture timestamps instead of speeding up dropped frames."""
    def __init__(self, path, size, fps=15):
        self.writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), fps, size)
        if not self.writer.isOpened():
            raise RuntimeError('Could not create the camera recording.')
        self.fps, self.start, self.count, self.previous = fps, None, 0, None

    def add(self, t, image):
        if self.start is None:
            self.start = t
        target = int(round((t - self.start) * self.fps))
        while self.count < target:
            self.writer.write(self.previous if self.previous is not None else image)
            self.count += 1
        if self.count == target:
            self.writer.write(image)
            self.count += 1
        self.previous = image

    def close(self):
        self.writer.release()


def review_crop(tracking, width, height):
    """Keep the tracked player's horizontal extent, with margin and full height."""
    points=[];tracked_frames=0
    for frame in tracking or []:
        if not frame.get('present') or 'xy' not in frame or 'scores' not in frame:
            continue
        xy=np.asarray(frame['xy']);scores=np.asarray(frame['scores'])
        valid=np.isfinite(xy).all(1)&np.isfinite(scores)&(scores>=.3)
        valid &= (xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=0)&(xy[:,1]<height)
        if valid.any():
            points.extend(xy[valid]);tracked_frames+=1
    if tracked_frames<10:
        return [0,0,1,1]
    xs=np.asarray(points)[:,0];left,right=float(xs.min()),float(xs.max())
    margin=max(width*.05,(right-left)*.15)
    return [max(0,(left-margin)/width),0,min(1,(right+margin)/width),1]


def save_review(root, path, options, completion="estimated_overhead_then_followthrough", tracking=None):
    job_id = str(uuid.uuid4())
    folder = root / job_id
    folder.mkdir()
    path.replace(folder / 'input')
    job = {'id': job_id, 'name': 'Live serve · ' + time.strftime('%H:%M:%S'),
           'created': int(time.time()*1000), 'status': 'preparing', 'stage': 'Preparing live recording',
           'view': options['view'], 'options': options,
           'capture': {'source': 'Ventuno USB webcam', 'tracking_backend': 'Host CPU · ONNX Runtime',
                       'completion': completion}}
    (folder / 'job.json').write_text(json.dumps(job))
    if tracking is not None:
        (folder / 'tracking.json').write_text(json.dumps(tracking, allow_nan=False))
    try:
        prepare(folder)
        prepared=json.loads((folder/'job.json').read_text())
        if options['crop']==[0,0,1,1]:
            crop=review_crop(tracking,prepared['meta']['width'],prepared['meta']['height'])
            if crop!=options['crop']:
                update(folder,options={**options,'crop':crop},
                       capture={**job['capture'],'crop_mode':'recorded_tracking_extent'})
    except Exception as exc:
        update(folder, status='failed', stage='Capture preparation failed', error=str(exc))
        raise
    return job_id


class JpegFrames:
    """Recover JPEG boundaries even if a diagnostic or damaged frame enters the pipe."""
    def __init__(self):
        self.buffer = b''

    def feed(self, chunk):
        self.buffer += chunk
        frames = []
        while True:
            start = self.buffer.find(b'\xff\xd8')
            if start < 0:
                self.buffer = self.buffer[-1:]
                break
            self.buffer = self.buffer[start:]
            end = self.buffer.find(b'\xff\xd9', 2)
            next_start = self.buffer.find(b'\xff\xd8', 2)
            if next_start >= 0 and (end < 0 or next_start < end):
                self.buffer = self.buffer[next_start:]
                continue
            if end < 0:
                if len(self.buffer) > 2_000_000:
                    self.buffer = self.buffer[-1:]
                break
            frames.append(self.buffer[:end+2])
            self.buffer = self.buffer[end+2:]
        return frames


class BoardCamera:
    """Latest-frame buffer: an inference delay never builds a stale preview queue."""
    def __init__(self, log):
        serial = os.environ.get('DJOKER_SERIAL', '242692658')
        self.proc = subprocess.Popen(['adb','-s',serial,'exec-out',
            'ffmpeg -nostdin -hide_banner -loglevel error -f v4l2 -input_format mjpeg '
            '-framerate 30 -video_size 640x480 -i /dev/video0 '
            '-an -c:v copy -f mjpeg -flush_packets 1 pipe:1'], stdout=subprocess.PIPE, stderr=log)
        self.latest = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        parser = JpegFrames()
        while True:
            chunk = self.proc.stdout.read1(65536)
            if not chunk:
                return
            frames = parser.feed(chunk)
            if not frames:
                continue
            frame = cv2.imdecode(np.frombuffer(frames[-1], np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.shape != (480,640,3):
                continue
            with self.lock:
                self.latest = (time.monotonic(), frame)

    def read(self):
        with self.lock:
            frame, self.latest = self.latest, None
            return frame

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.thread.join(timeout=2)
        self.proc.stdout.close()


def run(root, options):
    manual = options.pop('mode', 'auto') == 'manual'
    gate = ManualCapture() if manual else None
    trace = []
    live = root / 'live'
    live.mkdir(parents=True, exist_ok=True)
    # Process-level lease works across Next.js reloads and concurrent requests.
    with open(live/'capture.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        state = {'pid': os.getpid(), 'active': True, 'state': 'starting', 'message': 'Opening Ventuno camera…', 'jobId': None, 'mode': 'manual' if manual else 'auto'}
        def status(**fields):
            state.update(fields, updated=time.time())
            temp=live/'status.tmp';temp.write_text(json.dumps(state));temp.replace(live/'status.json')
        camera = recorder = None
        try:
            status()
            if not ONNX.exists():
                raise RuntimeError('Live tracking needs the local wholebody ONNX model (DJOKER_ONNX).')
            import onnxruntime as ort
            cfg=ort.SessionOptions();cfg.intra_op_num_threads=4
            model=ort.InferenceSession(str(ONNX),sess_options=cfg,providers=['CPUExecutionProvider'])
            if model.get_inputs()[0].shape != [1,3,256,192]:
                raise ValueError('Live tracking needs the wholebody RTMPose model.')
            with open(live/'camera.log','ab') as log:
                camera=BoardCamera(log)
                detector=ServeCapture() if manual else ReadyServeCapture(options['handedness'])
                player_crop=PlayerCrop(options['crop']);last=time.monotonic();message='Step into the player area with your whole body visible.'
                clip=live/'capture.avi'
                while not (live/'stop').exists():
                    frame=camera.read()
                    if frame is None:
                        if camera.proc.poll() is not None or time.monotonic()-last>5:
                            raise RuntimeError('Camera disconnected or unavailable. Check the USB webcam, then restart live capture.')
                        time.sleep(.01)
                        continue
                    stamp,image=frame
                    # A long transport/processing gap invalidates motion continuity.
                    if stamp-last>.5 and recorder and not manual:
                        recorder.close();recorder=None;clip.unlink(missing_ok=True)
                        detector.cancel()
                        message='Tracking paused. Start a fresh serve.'
                    last=stamp
                    tick=time.monotonic()
                    inference_crop=list(player_crop.box)
                    blob,matrix=crop_input(image,inference_crop)
                    px,py=model.run(None,{model.get_inputs()[0].name:blob})
                    xy,scores=decode(px,py,matrix)
                    inference_ms=(time.monotonic()-tick)*1000
                    present,overhead,lowered=pose_signal(xy,scores,640,480,options['handedness'])
                    # Pose must belong to the selected player area.
                    x1,y1,x2,y2=np.asarray(options['crop'])*[640,480,640,480]
                    center=xy[11:13].mean(0)
                    present=present and x1<=center[0]<=x2 and y1<=center[1]<=y2
                    ready=present and ready_pose(xy,scores,640,480)
                    observed=xy.copy()
                    visible=(np.isfinite(xy).all(1)&np.isfinite(scores)&(scores>=.5)
                             &(xy[:,0]>=0)&(xy[:,0]<640)&(xy[:,1]>=0)&(xy[:,1]<480))
                    observed[~visible]=np.nan
                    if not (x1<=center[0]<=x2 and y1<=center[1]<=y2):
                        observed[:]=np.nan
                    player_crop.update(stamp,xy,present,640,480)
                    auto_event=(detector.update(stamp,present,overhead,lowered) if manual
                                else detector.update(stamp,present,overhead,lowered,ready,pose=observed))
                    command=None
                    if manual and (live/'command.json').exists():
                        command=json.loads((live/'command.json').read_text())['action']
                        (live/'command.json').unlink(missing_ok=True)
                    event=gate.update(stamp,command) if manual else auto_event
                    if event=='start':
                        recorder=TimedRecording(clip,(640,480),30 if manual else 15)
                        recorder.add(stamp,image)
                        trace=[]
                        message='Manual recording · tracking loss will not stop this clip.' if manual else 'Recording · serve when ready.'
                    elif recorder:
                        recorder.add(stamp,image)
                    if recorder:
                        trace.append({'time':round(stamp-recorder.start,4),'present':bool(present),
                            'overhead':bool(overhead),'lowered':bool(lowered),'auto_state':detector.state,
                            'ready':bool(ready),
                            'finish_evidence':{} if manual else dict(detector.finish.evidence),
                            'auto_event':auto_event,'crop':inference_crop,'xy':np.nan_to_num(xy).tolist(),
                            'scores':np.nan_to_num(scores).tolist()})
                    if event in ('complete','discard') and recorder:
                        recorder.close();recorder=None
                        if event=='discard':
                            clip.unlink(missing_ok=True)
                            message='Attempt discarded: tracking lost or no complete motion within 18 seconds.'
                        else:
                            status(state='processing',message='Serve captured. Preparing your review…',countdown=None,readyProgress=0)
                            job_id=save_review(root,clip,options,gate.completion if manual else 'observed_reach_descent_recovery',trace)
                            status(jobId=job_id)
                            # Same worker, NPU backend and strict feedback gates as uploaded clips.
                            try:
                                process(root/job_id)
                                message='Review ready. Click Start recording for another clip.' if manual else 'Review ready. Reset for your next serve.'
                            except Exception as exc:
                                update(root/job_id,status='failed',stage='Processing stopped',error=str(exc))
                                message='Review failed. Open the saved clip to retry. '+str(exc)[-200:]
                            if manual:
                                detector=ServeCapture();detector.state='cooldown';detector.cooldown_until=time.monotonic()+2
                            else:
                                # Keep release/rearm state across the review processing pause.
                                detector.motion.cooldown_until=time.monotonic()+2
                            last=time.monotonic()
                    preview=image.copy()
                    cv2.rectangle(preview,(int(x1),int(y1)),(int(x2),int(y2)),(190,235,160),2)
                    for a,b in BONES:
                        if scores[a]>=.3 and scores[b]>=.3:
                            cv2.line(preview,tuple(xy[a].astype(int)),tuple(xy[b].astype(int)),(130,245,195),2)
                    for point,score in zip(xy,scores):
                        if score>=.3: cv2.circle(preview,tuple(point.astype(int)),3,(170,255,210),-1)
                    ok,jpeg=cv2.imencode('.jpg',preview,[cv2.IMWRITE_JPEG_QUALITY,80])
                    if ok:
                        temp=live/'preview.tmp';temp.write_bytes(jpeg.tobytes());temp.replace(live/'preview.jpg')
                    if manual and gate.state=='ready' and not state.get('jobId'):
                        message='Camera ready. Click Start recording, then perform one serve.'
                    if not manual and detector.state=='waiting':
                        if not present:
                            message='Step into the player area with your whole body visible.'
                        elif not detector.armed:
                            message='Lower your hand, then raise it to shoulder height for another attempt.'
                        elif ready:
                            message='Hold your hand at shoulder height…'
                        else:
                            message='Raise either hand to shoulder height and hold briefly to begin.'
                    if not manual and detector.state=='countdown':
                        message='Get ready to serve…' if present else 'Keep your whole body visible.'
                    if not manual and recorder and detector.saw_overhead:
                        message='Recording · waiting for the follow-through.'
                    status(state=gate.state if manual else detector.state,message=message,present=bool(present),
                           ready=bool(ready),countdown=None if manual else detector.countdown,
                           readyProgress=0 if manual else round(detector.ready_progress,3),
                           inference_ms=round(inference_ms,1),frame_to_preview_ms=round((time.monotonic()-stamp)*1000,1),elapsed=round(stamp-(gate.started if manual else detector.started),1) if recorder else 0)
        except Exception as exc:
            traceback.print_exc()
            status(state='error',message=str(exc))
        finally:
            if recorder:
                recorder.close()
                if manual:
                    try:
                        job_id=save_review(root,live/'capture.avi',options,'manual_interrupted',trace)
                        status(jobId=job_id,message='Camera stopped. Your unfinished clip was saved for review.')
                    except Exception:
                        traceback.print_exc()  # save_review preserves the input even if preparation fails
            (live/'capture.avi').unlink(missing_ok=True)
            if camera: camera.close()
            status(active=False,state='error' if state['state']=='error' else 'stopped',
                   message=state['message'] if state['state']=='error' else 'Live camera stopped.')


if __name__=='__main__':
    run(Path(sys.argv[1]).resolve(),json.loads(sys.argv[2]))
