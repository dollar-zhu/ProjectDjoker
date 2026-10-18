import json,subprocess,pathlib,hashlib
root=pathlib.Path(__file__).resolve().parent
(root/'samples').mkdir(exist_ok=True)
cases=json.loads((root/'cases.json').read_text())['cases']
items=[('p001','pro_federer.mp4',10,20,'reference'),('a001','amateur_bremen.mp4',13.8,16.3,'analysis'),('a004','amateur_sara.mp4',140.5,143.3,'analysis'),('a002','stephen_full.mp4',294,297,'view_rejection'),('a003','amateur_vishal.webm',180,184,'input_rejection')]
manifest={'created':'2026-10-17','purpose':'Local development samples, not held-out accuracy evaluation','clips':[],'pending':[{'source':'https://www.reddit.com/r/10s/comments/1jpkjlw/tennis_amateur_sharing_my_tennis_videos/','status':'Download unavailable: direct media and Reddit extraction refused. No footage substituted.'}]}
for id,src,start,end,role in items:
 c=next(x for x in cases if x['id']==id); offset=125 if src=='amateur_sara.mp4' else 0
 name=f"{id}_{c['subject'].lower()}.mp4"; dest=root/'samples'/name
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start-offset),'-i',str(root/'cache'/src),'-t',str(end-start),'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dest)])); v=probe['streams'][0]
 manifest['clips'].append({'id':id,'file':name,'subject':c['subject'],'source_url':c['url'],'source_start_s':start,'source_end_s':end,'source_cache_file':src,'cache_source_offset_s':offset,'role':role,'view':c['view'],'expected_response':c['expected_response'],'width':v['width'],'height':v['height'],'fps':v['avg_frame_rate'],'duration_s':float(probe['format']['duration']),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'audio':'removed','speed_note':'Source editing/slow motion preserved; not a true motion-timing benchmark.'})
(root/'samples'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
