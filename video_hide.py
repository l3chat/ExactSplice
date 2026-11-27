#!/usr/bin/env python3
"""Offline video redaction with FFmpeg. Full encode, or verified keyframe splice."""
import argparse, bisect, json, math, os, shutil, subprocess as sp, sys, tempfile
from pathlib import Path
from fractions import Fraction

def run(args):
    sp.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',*map(str,args)],check=True)
def probe(path, *args):
    return json.loads(sp.check_output(['ffprobe','-v','error',*args,'-of','json',str(path)]))
def keys(path):
    d=probe(path,'-select_streams','v:0','-skip_frame','nokey','-show_frames','-show_entries','frame=best_effort_timestamp_time')
    return sorted(set(float(f['best_effort_timestamp_time']) for f in d.get('frames',[]) if 'best_effort_timestamp_time' in f))
def seconds(s):
    try:
        p=list(map(float,s.split(':')))
        if not 1<=len(p)<=3 or any(x<0 or not math.isfinite(x) for x in p): raise ValueError()
        return sum(x*60**i for i,x in enumerate(reversed(p)))
    except ValueError: raise argparse.ArgumentTypeError('Use seconds, MM:SS or HH:MM:SS')
def fmt(t): return f'{t:.9f}'
def fontpath():
    for p in ['/system/fonts/Roboto-Regular.ttf','/system/fonts/RobotoStatic-Regular.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',str(Path(os.environ.get('PREFIX','/usr'))/'share/fonts/TTF/DejaVuSans.ttf')]:
        if Path(p).is_file(): return p
    raise ValueError('No font found; specify --font /path/to/font.ttf')
def timer(end,font,enable=''):
    left=f'max(0,ceil({fmt(end)}-t))'
    text=r'%{eif\:floor('+left+r'/3600)\:d\:2}\:%{eif\:mod(floor('+left+r'/60),60)\:d\:2}\:%{eif\:mod('+left+r',60)\:d\:2}'
    return f"drawtext=fontfile='{font}':text='{text}':fontsize=h/9:fontcolor=0x333333:x=(w-tw)/2:y=(h-th)/2"+enable

def hashes(p):
    out=sp.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:v:0','-an','-f','framemd5','-'],text=True)
    return [x.split(',')[-1].strip() for x in out.splitlines() if x and not x.startswith('#')]
def audio_args(mute,a,b):
    return ['-af',f"volume=0:enable='gte(t,{fmt(a)})*lt(t,{fmt(b)})'",'-c:a','aac','-b:a','192k'] if mute else ['-c:a','copy']
def full(src,dst,a,b,opt,font,has_audio):
    e=f":enable='gte(t,{fmt(a)})*lt(t,{fmt(b)})'"
    vf=f'drawbox=color=0xD9D9D9:t=fill{e},'+timer(b,font,e)
    run(['-i',src,'-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-map_chapters','-1','-vf',vf,'-c:v','libx264','-crf',str(opt.crf),'-preset','fast','-fps_mode','passthrough',*audio_args(opt.mute and has_audio,a,b),dst])
def smart(src,dst,a,b,opt,font,v,duration,has_audio):
    if v.get('codec_name')!='h264' or v.get('pix_fmt')!='yuv420p' or v.get('sample_aspect_ratio','1:1') not in ('1:1','0:1') or v.get('side_data_list') or abs(float(v.get('start_time',0)))>0.000001:
        raise ValueError('Smart mode requires ordinary H.264 yuv420p, square pixels, zero video start, no side data')
    fps=Fraction(v['avg_frame_rate']); rate=Fraction(v['r_frame_rate'])
    if fps!=rate or fps<=0: raise ValueError('Smart mode requires constant frame rate')
    k=keys(src); i=bisect.bisect_right(k,a)-1; j=bisect.bisect_left(k,b)
    if i<0 or j>=len(k): raise ValueError('No safe pair of keyframes (use full mode)')
    aa,bb=k[i],k[j]
    if aa<=0 or bb>=duration: raise ValueError('Smart mode requires nonempty original parts on both sides')
    n0,n1=round(aa*fps),round(bb*fps)
    if abs(float(n0/fps)-aa)>0.00001 or abs(float(n1/fps)-bb)>0.00001: raise ValueError('Keyframes not on CFR grid')
    print(f'Expanded interval: {aa:.6f} – {bb:.6f} s',flush=True)
    with tempfile.TemporaryDirectory(prefix='video-hide-') as td:
        p=Path(td); pattern=p/'part%02d.mp4'
        run(['-i',src,'-map','0:v:0','-c','copy','-f','segment','-segment_times',f'{fmt(aa)},{fmt(bb)}','-segment_time_delta','0.000001','-reset_timestamps','1',pattern])
        parts=sorted(p.glob('part*.mp4'))
        if len(parts)!=3: raise ValueError('Unexpected number of segments')
        # Generate replacement independently; no confidential input pixels.
        mid=p/'gray.mp4'; dur=float((n1-n0)/fps)
        run(['-f','lavfi','-i',f'color=c=0xD9D9D9:s={v["width"]}x{v["height"]}:r={fps}','-vf',timer(dur,font),'-frames:v',str(n1-n0),'-c:v','libx264','-pix_fmt','yuv420p','-crf',str(opt.crf),'-preset','fast','-video_track_timescale',str(Fraction(v['time_base']).denominator),mid])
        lst=p/'list.txt'; lst.write_text(f"file 'part00.mp4'\nduration {fmt(float(n0/fps))}\nfile 'gray.mp4'\nduration {fmt(dur)}\nfile 'part02.mp4'\n")
        joined=p/'joined.mp4'
        run(['-f','concat','-safe','1','-i',lst,'-c','copy',joined])
        print('Verifying every decoded video frame (may take time)...',flush=True)
        original=hashes(src); replacement=hashes(mid); expected=original[:n0]+replacement+original[n1:]
        if len(replacement)!=n1-n0 or hashes(joined)!=expected: raise ValueError('Splice verification failed; no output published')
        run(['-i',joined,'-i',src,'-map','0:v:0','-map','1:a:0?','-map_metadata','-1','-map_chapters','-1','-c:v','copy',*audio_args(opt.mute and has_audio,aa,bb),dst])
        if hashes(dst)!=expected: raise ValueError('Final frame verification failed')

def main():
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='cmd',required=True)
    k=sub.add_parser('keys'); k.add_argument('input'); k.add_argument('--near',type=seconds)
    h=sub.add_parser('hide'); h.add_argument('input'); h.add_argument('output'); h.add_argument('start',type=seconds); h.add_argument('end',type=seconds); h.add_argument('--smart',action='store_true',help='experimental verified splice; expands interval, fails closed'); h.add_argument('--mute',action='store_true'); h.add_argument('--font'); h.add_argument('--crf',type=int,default=18)
    o=ap.parse_args(); src=Path(o.input).resolve()
    if o.cmd=='keys':
        kk=keys(src)
        if o.near is not None:
            i=bisect.bisect_left(kk,o.near); kk=kk[max(0,i-3):i+4]
        for t in kk: print(f'{t:12.6f} s  ({int(t//3600):02}:{int(t//60)%60:02}:{t%60:09.6f})')
        return
    dst=Path(o.output).resolve()
    if dst==src or dst.exists() or dst.suffix.lower()!='.mp4': raise ValueError('Choose a new MP4 output filename')
    info=probe(src,'-show_streams','-show_format'); v=next(x for x in info['streams'] if x['codec_type']=='video'); duration=float(info['format']['duration']); has_audio=any(x['codec_type']=='audio' for x in info['streams'])
    if not 0<=o.start<o.end<=duration or not 0<=o.crf<=51: raise ValueError('Invalid interval or CRF')
    font=o.font or fontpath()
    if any(c in font for c in "'\\:,;[]"): raise ValueError('Use a simple font path')
    with tempfile.TemporaryDirectory(dir=dst.parent,prefix='.video-hide-') as td:
        tmp=Path(td)/'result.mp4'
        if o.smart: smart(src,tmp,o.start,o.end,o,font,v,duration,has_audio)
        else: full(src,tmp,o.start,o.end,o,font,has_audio)
        os.replace(tmp,dst)
    print('Saved:',dst)
if __name__=='__main__':
    try: main()
    except (ValueError, OSError, sp.CalledProcessError, StopIteration, KeyError) as e:
        print('ERROR:',e,file=sys.stderr); sys.exit(1)
