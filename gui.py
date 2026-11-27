#!/usr/bin/env python3
import json, os, secrets, subprocess, sys, threading, urllib.parse, mimetypes
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import video_hide as core
import signal,time
from timeline import Timeline, Clip
from fractions import Fraction
from render_timeline import source_info
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else str(Path.home()/'storage/shared')).resolve()
HERE=Path(__file__).resolve().parent
TOKEN=secrets.token_urlsafe(24)
lock=threading.Lock(); job={'state':'idle','log':''}; proc=None

def path(s):
 p=(ROOT/s).resolve(); p.relative_to(ROOT); return p

def work(args, script='multi.py'):
 global proc
 try:
  proc=subprocess.Popen([sys.executable,'-u',str(HERE/script),*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
  with lock:
   if job['state']=='cancelling': os.killpg(proc.pid,signal.SIGTERM)
  for line in proc.stdout:
   with lock:
    if line.startswith('STATUS '): job.update(json.loads(line[7:]))
    elif line.startswith('PROGRESS '): job['progress']=max(job.get('progress',0),float(line.split()[1]))
    else: job['log']=(job['log']+line)[-20000:]
  code=proc.wait()
  with lock: job['state']='done' if code==0 else ('cancelled' if job['state']=='cancelling' else 'error'); job['elapsed']=time.monotonic()-job['started']
 except Exception as e:
  with lock: job.update(state='error',log=str(e))

class Handler(BaseHTTPRequestHandler):
 def reply(self,obj,status=200):
  b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  try:
   u=urllib.parse.urlsplit(self.path); q=urllib.parse.parse_qs(u.query); get=lambda k,d='':q.get(k,[d])[0]
   if u.path in ('/','/editor'):
    b=(HERE/('editor.html' if u.path=='/editor' else 'index.html')).read_text().replace('__TOKEN__',TOKEN).encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b); return
   if get('token')!=TOKEN: self.reply({'error':'Forbidden'},403); return
   if u.path=='/list':
    p=path(get('dir')); items=[]
    for x in sorted(p.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower())):
     try: rel=str(x.resolve().relative_to(ROOT))
     except ValueError: continue
     if x.is_dir() or x.suffix.lower() in ('.mp4','.mkv','.mov','.webm','.m4v','.avi'): items.append({'name':x.name,'path':rel,'dir':x.is_dir()})
    self.reply({'items':items,'parent':str(p.parent.relative_to(ROOT)) if p!=ROOT else None}); return
   if u.path=='/info':
    p=path(get('file')); d=core.probe(p,'-show_streams','-show_format'); v=next(x for x in d['streams'] if x['codec_type']=='video'); self.reply({'duration':float(d['format']['duration']),'fps':v['avg_frame_rate'],'size':p.stat().st_size,'codec':v['codec_name']}); return
   if u.path=='/source':
    self.reply(source_info(path(get('file')))); return
   if u.path=='/keys':
    p=path(get('file')); self.reply({'keys':core.keys(p)}); return
   if u.path=='/status':
    with lock:
     data=dict(job)
     if data['state'] in ('running','cancelling'): data['elapsed']=time.monotonic()-data['started']
    self.reply(data); return
   if u.path=='/video':
    p=path(get('file')); size=p.stat().st_size; a=0;b=size-1; r=self.headers.get('Range'); status=200
    if r:
     import re
     m=re.fullmatch(r'bytes=(\d*)-(\d*)',r)
     if not m: self.send_error(416); return
     a=int(m[1]) if m[1] else max(0,size-int(m[2])); b=min(b,int(m[2])) if m[1] and m[2] else b; status=206
     if a>b or a>=size: self.send_error(416); return
    self.send_response(status); self.send_header('Content-Type',mimetypes.guess_type(p.name)[0] or 'application/octet-stream'); self.send_header('Accept-Ranges','bytes'); self.send_header('Content-Length',str(b-a+1));
    if status==206: self.send_header('Content-Range',f'bytes {a}-{b}/{size}')
    self.end_headers()
    with p.open('rb') as f:
     f.seek(a); n=b-a+1
     while n:
      buf=f.read(min(n,262144));
      if not buf: break
      self.wfile.write(buf); n-=len(buf)
    return
   self.reply({'error':'Not found'},404)
  except (BrokenPipeError,ConnectionResetError): pass
  except Exception as e: self.reply({'error':str(e)},400)
 def do_POST(self):
  try:
   if self.path not in ('/start','/cancel','/edit','/render') or self.headers.get('X-Token')!=TOKEN: self.reply({'error':'Forbidden'},403); return
   if self.path=='/cancel':
    with lock:
     if job['state']=='running':
      job['state']='cancelling'
      if proc is not None and proc.poll() is None: os.killpg(proc.pid,signal.SIGTERM)
    self.reply({'ok':True}); return
   length=int(self.headers['Content-Length'])
   if not 0<=length<=2_000_000: raise ValueError('Request too large')
   d=json.loads(self.rfile.read(length))
   if self.path=='/edit':
    op=d['op']
    if op=='new':
     s=source_info(path(d['file'])); t=Timeline(s['fps'],[Clip(d['file'],0,s['frames'])])
    elif op=='legacy':
     p=d['project']; s=source_info(path(p['file'])); t=Timeline.from_legacy(p,s['fps'],s['frames'])
    else:
     t=Timeline.from_dict(d['project'])
     a=d.get('a'); b=d.get('b'); pos=d.get('position')
     clipboard=None
     if op=='copy': clipboard=t.copy(a,b)
     elif op=='cut': clipboard=t.cut(a,b)
     elif op=='delete': t.delete(a,b)
     elif op=='hide': t.hide(a,b,d.get('mute',True))
     elif op=='move': t.move(a,b,pos)
     elif op=='split': t.split(pos)
     elif op in ('paste','replace'):
      clips=[Clip(**c) for c in d['clipboard']]
      if op=='paste': t.paste(pos,clips)
      else: t.replace(a,b,clips)
     elif op=='insert':
      s=source_info(path(d['file']))
      if Fraction(s['fps'])!=t.fps: raise ValueError('Different frame rate: normalize source first')
      if not 0<=a<b<=s['frames']: raise ValueError('Invalid source selection')
      t.insert(pos,[Clip(d['file'],a,b)])
     else: raise ValueError('Unknown edit')
     self.reply({'project':t.to_dict(),'clipboard':[vars(c) for c in clipboard] if clipboard is not None else None}); return
    self.reply({'project':t.to_dict()}); return
   if self.path=='/render':
    t=Timeline.from_dict(d['project']); dst=path(d['output'])
    if not t.clips or dst.exists() or not dst.parent.is_dir() or dst.suffix.lower()!='.mp4': raise ValueError('Choose new MP4 output and nonempty timeline')
    project=t.to_dict()
    for clip in project['timeline']: clip['source']=str(path(clip['source']))
    args=[json.dumps({'project':project,'output':str(dst),'crf':int(d.get('crf',18)),'mode':d.get('mode','full')})]
    with lock:
     if job['state'] in ('running','cancelling'): self.reply({'error':'Already running'},409); return
     job.clear(); job.update(state='running',log='Starting timeline export…\n',progress=0,started=time.monotonic())
    threading.Thread(target=work,args=(args,'render_timeline.py'),daemon=True).start(); self.reply({'ok':True}); return
   src=path(d['file']); dst=path(d['output']); a=0; b=1; crf=int(d.get('crf',18))
   if not src.is_file() or dst.exists() or not dst.parent.is_dir() or dst.suffix.lower()!='.mp4' or not 0<=a<b or not 0<=crf<=51: raise ValueError('Invalid input/output/interval')
   d.update(file=str(src),output=str(dst)); args=[json.dumps(d)]
   with lock:
    if job['state'] in ('running','cancelling'): self.reply({'error':'Already running'},409); return
    job.clear(); job.update(state='running',log='Starting FFmpeg…\n',progress=0,started=time.monotonic())
   threading.Thread(target=work,args=(args,),daemon=True).start(); self.reply({'ok':True})
  except Exception as e: self.reply({'error':str(e)},400)
if __name__=='__main__':
 if not ROOT.is_dir(): sys.exit('Storage not found. Run termux-setup-storage or supply a directory.')
 server=ThreadingHTTPServer(('127.0.0.1',8765),Handler); print('Open http://127.0.0.1:8765 — root:',ROOT,flush=True)
 try: server.serve_forever()
 except KeyboardInterrupt:
  if proc is not None and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM); proc.wait()
  server.server_close()
