"""Clip inbox for the Ventuno Q: stdlib HTTP server with a phone-friendly upload form (POST multipart) and a directory
listing (GET). Run on the board: python3 inbox_server.py [--dir ~/inbox] [--port 8000]; phones on the tailnet open
http://team-ventuno:8000/ (or http://100.74.60.29:8000/). curl: curl -F clip=@serve.mp4 http://team-ventuno:8000/upload"""
import argparse, os, re, time, json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
ap = argparse.ArgumentParser(); ap.add_argument("--dir", default=os.path.expanduser("~/inbox")); ap.add_argument("--port", type=int, default=8000); a = ap.parse_args()
os.makedirs(a.dir, exist_ok=True)
FORM = b"""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><h2>Ventuno clip inbox</h2>
<form method=post action=/upload enctype=multipart/form-data><input type=file name=clip accept="video/*" capture=environment><br><br>
<button style="font-size:1.4em">Upload</button></form><p><a href=/files/>files</a></p>"""
class H(SimpleHTTPRequestHandler):
    def __init__(s, *x, **k): super().__init__(*x, directory=a.dir, **k)
    def do_GET(s):
        if s.path == "/": s.send_response(200); s.send_header("Content-Type", "text/html"); s.end_headers(); s.wfile.write(FORM)
        elif s.path.startswith("/files"): s.path = s.path[6:] or "/"; super().do_GET()
        else: s.send_error(404)
    def do_POST(s):
        n = int(s.headers["Content-Length"]); ct = s.headers.get("Content-Type", ""); m = re.search(r"boundary=([^;]+)", ct)
        if not m: s.send_error(400, "multipart/form-data expected"); return
        t0 = time.time(); body = s.rfile.read(n); b = b"--" + m.group(1).strip('"').encode()
        for part in body.split(b)[1:-1]:
            head, _, data = part.partition(b"\r\n\r\n"); fn = re.search(rb'filename="([^"]*)"', head)
            if not fn or not fn.group(1): continue
            name = time.strftime("%Y%m%d-%H%M%S_") + re.sub(r"[^\w.\-]", "_", fn.group(1).decode(errors="replace")); p = os.path.join(a.dir, name)
            open(p, "wb").write(data[:-2] if data.endswith(b"\r\n") else data)
            r = {"saved": name, "bytes": os.path.getsize(p), "seconds": round(time.time() - t0, 3)}; print(json.dumps(r), flush=True)
            s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers(); s.wfile.write(json.dumps(r).encode()); return
        s.send_error(400, "no file field")
print("inbox", a.dir, "port", a.port, flush=True); ThreadingHTTPServer(("0.0.0.0", a.port), H).serve_forever()
