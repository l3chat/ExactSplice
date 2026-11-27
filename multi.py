import video_hide as c
import sys,json,math,bisect,tempfile,os,subprocess as sp,signal,time,re
from pathlib import Path
from fractions import Fraction

def merge(rs):
 out=[]
 for a,b in sorted(rs):
  if out and a<=out[-1][1]: out[-1][1]=max(b,out[-1][1])
  else: out.append([a,b])
 return out

def emit(**kw): print('STATUS '+json.dumps(kw,ensure_ascii=False),flush=True)
def cancel(sig,frame): raise KeyboardInterrupt
signal.signal(signal.SIGTERM,cancel)

def main(d):
 src=Path(d['file']); dst=Path(d['output']); emit(stage='Анализ исходного файла',progress=0); info=c.probe(src,'-show_streams','-show_format'); v=next(s for s in info['streams'] if s['codec_type']=='video'); dur=float(info['format']['duration']); rs=merge(d['intervals']); color=d.get('color','#d9d9d9'); fg=d.get('fg','#333333'); size=int(d.get('size',11)); crf=int(d.get('crf',18)); mode=d.get('mode','smart' if d.get('smart') else 'full'); verify=bool(d.get('verify',False))
 if mode not in ('full','smart','exact') or not all(re.fullmatch(r'#[0-9a-fA-F]{6}',x) for x in [color,fg]) or not 2<=size<=30 or not 0<=crf<=51 or not rs or not all(0<=a<b<=dur for a,b in rs): raise ValueError('Invalid settings or intervals')
 if dst.exists() or src.resolve()==dst.resolve(): raise ValueError('Output exists')
 font=c.fontpath(); fps=Fraction(v['avg_frame_rate']); audio=any(s['codec_type']=='audio' for s in info['streams']); common=['-map_metadata','-1','-map_chapters','-1']
 def timer(end,e=''):
  return c.timer(end,font,e).replace('fontsize=h/9',f'fontsize=h*{size}/100').replace('fontcolor=0x333333','fontcolor=0x'+fg[1:])
 def filters(ranges):
  out=[]
  for a,b in ranges:
   e=f":enable='gte(t,{a:.9f})*lt(t,{b:.9f})'"; out+=['drawbox=color=0x'+color[1:]+':t=fill'+e,timer(b,e)]
  return ','.join(out)
 def run(args,stage,base,span,length=dur):
  emit(stage=stage,progress=base,speed='',bytes=None,stage_progress=0)
  print('FFmpeg:', ' '.join(map(str,args)),flush=True)
  p=sp.Popen(['ffmpeg','-hide_banner','-loglevel','warning','-xerror','-nostdin','-y','-progress','pipe:1','-nostats',*map(str,args)],stdout=sp.PIPE,text=True)
  try:
   stats={}
   for line in p.stdout:
    k,_,val=line.strip().partition('='); stats[k]=val
    if k=='progress':
     try: f=1 if val=='end' else min(1,max(0,int(stats.get('out_time_us','0'))/1e6/max(length,.001)))
     except ValueError: f=0
     emit(progress=min(99,base+span*f),stage_progress=100*f,speed=stats.get('speed',''),bytes=int(stats['total_size']) if stats.get('total_size','').isdigit() else None)
   if p.wait(): raise RuntimeError('FFmpeg failed')
  finally:
   if p.poll() is None: p.terminate(); p.wait()
 def audio_args(ranges):
  if not audio or not d.get('mute'): return ['-c:a','copy']
  expr='+'.join(f'between(t,{max(0,a-.25):.9f},{b+.25:.9f})' for a,b in ranges)
  return ['-af',f"volume=0:enable='{expr}'",'-c:a','aac','-b:a','192k']
 def digest(path,stage,base,span,length,seek=None,count=None):
  f=p/'hash.txt'; args=[] if seek is None else ['-ss',c.fmt(seek)]
  run([*args,'-i',path,'-map','0:v:0','-an',*(['-frames:v',count] if count else []),'-f','framemd5',f],stage,base,span,length)
  return [x.split(',')[-1].strip() for x in f.read_text().splitlines() if x and not x.startswith('#')]
 def packet_count(path, expected=None, offset=0):
  # Validate presentation grid, including reordered B frames. Packet count alone is insufficient.
  if expected is None:
   data=c.probe(path,'-select_streams','v:0','-count_packets','-show_entries','stream=nb_read_packets');return int(data['streams'][0]['nb_read_packets'])
  ticks=bytearray(expected); n=0
  pp=sp.Popen(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts_time','-of','csv=p=0',str(path)],stdout=sp.PIPE,text=True)
  try:
   for line in pp.stdout:
    t=float(line.strip().split(',')[0])-offset; ix=round(t*fps)
    if not 0<=ix<expected or abs(t-float(ix/fps))>0.000002 or ticks[ix]: raise ValueError('Non-CFR or shifted presentation timestamps; use Full')
    ticks[ix]=1;n+=1
    if n%5000==0: emit(stage_progress=100*n/expected)
   if pp.wait(): raise ValueError('Packet scan failed')
   return n
  finally:
   if pp.poll() is None: pp.terminate(); pp.wait()
 with tempfile.TemporaryDirectory(dir=dst.parent,prefix='.video-hide-') as td:
  p=Path(td); result=p/'result.mp4'
  if mode=='full':
   run(['-i',src,'-map','0:v:0','-map','0:a:0?',*common,'-vf',filters(rs),'-c:v','libx264','-crf',crf,'-preset','fast','-fps_mode','passthrough',*audio_args(rs),result],'Полное перекодирование',2,93)
   if verify: digest(result,'Проверка декодирования (Full)',95,4,dur)
  else:
   if v.get('codec_name')!='h264' or v.get('pix_fmt')!='yuv420p' or v.get('sample_aspect_ratio','1:1') not in ('1:1','0:1') or v.get('side_data_list') or abs(float(v.get('start_time',0)))>1e-6 or fps<=0 or fps!=Fraction(v['r_frame_rate']): raise ValueError('Smart requires ordinary CFR H.264 yuv420p, zero start, square pixels')
   emit(stage='Поиск ключевых кадров',progress=2); k=c.keys(src); expanded=[]
   for a,b in rs:
    i=bisect.bisect_right(k,a)-1;j=bisect.bisect_left(k,b)
    if i<0 or j>=len(k): raise ValueError('No safe keyframe boundaries; use full mode')
    expanded.append([k[i],k[j]])
   blocks=merge(expanded); cuts=[x for r in blocks for x in r]; ns=[round(x*fps) for x in cuts]
   if cuts[0]<=0 or cuts[-1]>=dur or any(abs(float(n/fps)-x)>1e-5 for n,x in zip(ns,cuts)): raise ValueError('Smart requires interior CFR keyframes; use full mode')
   print('Expanded:',blocks,flush=True)
   run(['-i',src,'-map','0:v:0','-c','copy','-f','segment','-segment_times',','.join(map(c.fmt,cuts)),'-segment_time_delta','0.000001','-reset_timestamps','1',p/'part%03d.mp4'],'Разделение исходного видео',5,15)
   parts=sorted(p.glob('part*.mp4'))
   if len(parts)!=len(cuts)+1: raise ValueError('Unexpected segment count')
   total=round(float(v.get('duration',dur))*fps); edges=[0,*ns,total]; lengths=[b-a for a,b in zip(edges,edges[1:])]
   emit(stage='Проверка числа пакетов',progress=20)
   for idx,(part,n) in enumerate(zip(parts,lengths)):
    emit(stage=f'Проверка пакетов {idx+1}/{len(parts)}',stage_progress=0)
    offset=float(c.probe(part,'-select_streams','v:0','-show_entries','stream=start_time')['streams'][0].get('start_time',0)) if idx==0 else 0
    if packet_count(part,n,offset)!=n: raise ValueError('Unexpected packet count; use Full')
   selected=parts[:]; effective=blocks if mode=='smart' else rs
   for i,(a,b) in enumerate(blocks):
    n0,n1=ns[2*i:2*i+2]; mid=p/f'gray{i}.mp4'; length=float((n1-n0)/fps); base=22+38*i/len(blocks); span=38/len(blocks)
    enc=['-r',str(fps),'-fps_mode','cfr','-frames:v',n1-n0,'-c:v','libx264','-pix_fmt','yuv420p','-crf',crf,'-preset','fast','-video_track_timescale',Fraction(v['time_base']).denominator]
    if mode=='smart': args=['-f','lavfi','-i',f'color=c=0x{color[1:]}:s={v["width"]}x{v["height"]}:r={fps}','-vf',timer(length)]
    else:
     # Use frame-index intervals, not rounded local timestamps; generate gray pixels independently via drawbox.
     local=[]; force=[]
     for x,y in rs:
      if x<b and y>a:
       l=max(0,math.ceil(x*fps-1e-8)-n0); r=min(n1-n0,math.ceil(y*fps-1e-8)-n0)
       if l<r: local.append((l,r));force.extend([l,r])
     fs=['settb=expr='+str(1/fps),'setpts=N']
     for l,r in local:
      e=f":enable='gte(n,{l})*lt(n,{r})'";fs+=['drawbox=color=0x'+color[1:]+':t=fill'+e,timer(float(r/fps),e)]
     args=['-i',parts[2*i+1],'-vf',','.join(fs),'-force_key_frames',','.join(c.fmt(float(n/fps)) for n in sorted(set([0,*force])) if n<n1-n0),'-forced-idr','1','-x264-params','open-gop=0']
    run([*args,*enc,mid],f'Создание фрагмента {i+1}/{len(blocks)}',base,span,length)
    if packet_count(mid,n1-n0)!=n1-n0: raise ValueError('Replacement frame count')
    selected[2*i+1]=mid
   lst=p/'list.txt';lst.write_text(''.join(f"file '{part.name}'\nduration {float(n/fps):.9f}\n" for part,n in zip(selected,lengths)))
   # Normalize decode timestamps across segments with different B-frame reorder delays.
   # Keep presentation timestamps and compressed picture data unchanged.
   tb=Fraction(v['time_base']); step=1/fps/tb
   if step.denominator!=1: raise ValueError('Nonintegral frame duration in source time base; use Full')
   delay=0
   for i,part in enumerate(selected):
    emit(stage=f'Анализ DTS {i+1}/{len(selected)}',progress=60,stage_progress=0)
    q=sp.Popen(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts','-of','csv=p=0',str(part)],stdout=sp.PIPE,text=True)
    try:
     ptb=Fraction(c.probe(part,'-select_streams','v:0','-show_entries','stream=time_base')['streams'][0]['time_base'])
     n=0
     for line in q.stdout:
      pts=int(line.strip().split(',')[0])
      # PTS minimum is zero (validated earlier), except initial segment offset.
      origin=Fraction(str(c.probe(part,'-select_streams','v:0','-show_entries','stream=start_time')['streams'][0].get('start_time',0))) if n==0 else origin
      delay=max(delay,math.ceil(n-(pts*ptb-origin)*fps)); n+=1
      if n%5000==0: emit(stage_progress=100*n/lengths[i])
     if q.wait() or n!=lengths[i]: raise ValueError('DTS scan failed')
    finally:
     if q.poll() is None: q.terminate(); q.wait()
   print('Common decode delay (frames):',delay,flush=True)
   bsf=f'setts=pts=PTS:dts=(N-{delay})*{int(step)}:duration={int(step)}'
   joined=p/'joined.mp4';run(['-f','concat','-safe','1','-i',lst,'-c','copy','-bsf:v',bsf,'-video_track_timescale',tb.denominator,joined],'Склейка фрагментов',60,10)
   run(['-i',joined,'-i',src,'-map','0:v:0','-map','1:a:0?',*common,'-c:v','copy',*audio_args(effective),result],'Добавление звука',70,12)
   emit(stage='Проверка структуры',progress=82)
   if packet_count(result,total)!=total: raise ValueError('Final packet count mismatch')
   if verify:
    expected=[]
    for i,(part,n) in enumerate(zip(selected,lengths)):
     expected+=digest(part,f'Контрольные суммы фрагмента {i+1}/{len(selected)}',82+7*edges[i]/total,7*n/total,float(n/fps))
    actual=digest(result,'Полная покадровая проверка',89,10,dur)
    if actual!=expected: raise ValueError('Final frame verification failed')
   else:
    # Verify decoded frames on both sides of each splice against independently decoded segments.
    for i in range(1,len(selected)):
     emit(stage=f'Проверка границы {i}/{len(selected)-1}',progress=82+17*(i-1)/(len(selected)-1))
     for j,offset in [(i-1,max(0,lengths[i-1]-3)),(i,0)]:
      count=min(3,lengths[j]-offset); t=float(offset/fps); base=82+17*(i-1)/(len(selected)-1)
      expected=digest(selected[j],f'Граница {i}/{len(selected)-1}: фрагмент',base,0,count/float(fps),t,count)
      actual=digest(result,f'Граница {i}/{len(selected)-1}: результат',base,0,count/float(fps),float((edges[j]+offset)/fps),count)
      if len(expected)!=count or expected!=actual: raise ValueError('Boundary verification failed; use Full')
  if dst.exists(): raise ValueError('Output appeared during processing')
  os.replace(result,dst)
 emit(progress=100,stage='Готово');print('Saved:',dst,flush=True)
if __name__=='__main__':
 try: main(json.loads(sys.argv[1]))
 except KeyboardInterrupt: print('Cancelled',flush=True);sys.exit(130)
 except Exception as e: print('ERROR:',e,flush=True);sys.exit(1)
