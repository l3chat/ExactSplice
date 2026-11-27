"""Timeline renderer with explicit Full and experimental Smart Exact modes."""
import json, os, signal, subprocess, sys, tempfile
from fractions import Fraction
from pathlib import Path
from timeline import Timeline
import video_hide as core

def source_info(p):
    d=core.probe(p,'-show_streams','-show_format')
    v=next(s for s in d['streams'] if s['codec_type']=='video')
    fps=Fraction(v['avg_frame_rate'])
    if fps<=0 or fps!=Fraction(v['r_frame_rate']) or abs(float(v.get('start_time',0)))>1e-6:
        raise ValueError('Only zero-start CFR sources supported')
    if v.get('side_data_list') or v.get('sample_aspect_ratio','1:1') not in ('1:1','0:1'):
        raise ValueError('Rotated or non-square-pixel sources not supported yet')
    frames=int(v.get('nb_frames','0'))
    if frames<=0: raise ValueError('Source needs an explicit frame count (MP4 recommended)')
    a=next((s for s in d['streams'] if s['codec_type']=='audio'),None)
    if a and abs(float(a.get('start_time',0)))>1e-6: raise ValueError('Nonzero audio start not supported')
    return dict(fps=str(fps),frames=frames,width=v['width'],height=v['height'],audio=a is not None)

def emit(**kw):
    print('STATUS '+json.dumps(kw),flush=True)

def run(args,stage,base,span,seconds):
    emit(stage=stage,progress=base,stage_progress=0)
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-xerror','-nostdin','-y','-progress','pipe:1','-nostats',*map(str,args)]
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,text=True)
    try:
        for line in p.stdout:
            k,_,v=line.strip().partition('=')
            if k=='out_time_us':
                try: f=max(0,min(1,int(v)/1e6/max(seconds,.001)))
                except ValueError: continue
                emit(progress=base+span*f,stage_progress=100*f)
            elif k=='speed': emit(speed=v)
        if p.wait(): raise RuntimeError('FFmpeg failed: '+stage)
    finally:
        if p.poll() is None: p.terminate(); p.wait()
        p.stdout.close()

def render(data):
    t=Timeline.from_dict(data['project']); dst=Path(data['output']).resolve()
    crf=int(data.get('crf',18))
    if not t.clips or dst.exists() or dst.suffix.lower()!='.mp4' or not 0<=crf<=51: raise ValueError('Invalid export')
    mode=data.get('mode','full')
    if mode not in ('full','smart'): raise ValueError('Unknown export mode')
    sources={}
    for c in t.clips:
        if c.source not in sources: sources[c.source]=source_info(c.source)
        s=sources[c.source]
        if Fraction(s['fps'])!=t.fps or c.end>s['frames']: raise ValueError('Source frame rate or range mismatch')
    first=sources[t.clips[0].source]; w,h=first['width'],first['height']
    if w%2 or h%2: raise ValueError('Even project dimensions required')
    # First clip defines resolution. Other sources are fitted with letterboxing.
    fps=t.fps; total=t.length; seconds=float(total/fps); elapsed=0
    with tempfile.TemporaryDirectory(dir=dst.parent,prefix='.exactsplice-') as td:
        p=Path(td); parts=[]; pcm=p/'audio.raw'
        smart_video=None; expected=None
        if mode=='smart':
            from smart_engine import render_video
            smart_video,expected=render_video(t,sources,p,crf,emit)
        with pcm.open('wb') as audio:
            for i,c in enumerate(t.clips):
                s=sources[c.source]; n=c.length; dur=float(n/fps); out=p/f'v{i:05d}.mp4'
                a=float(c.start/fps); b=float(c.end/fps)
                base=90*elapsed/total; span=90*n/total
                if mode=='smart': base=60+30*elapsed/total; span=30*n/total
                if mode=='full':
                    vf=f'trim=start_frame={c.start}:end_frame={c.end},settb=expr={1/fps},setpts=N,scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1'
                    if c.hidden:
                        # Generate replacement from scratch: no source video pixels enter this segment.
                        vin=['-f','lavfi','-i',f'color=c=0xd9d9d9:s={w}x{h}:r={fps}']
                        vf=core.timer(dur,core.fontpath())
                    else: vin=['-i',c.source]
                    run([*vin,'-map','0:v:0','-an','-vf',vf,'-frames:v',n,'-r',str(fps),'-fps_mode','cfr','-c:v','libx264','-pix_fmt','yuv420p','-crf',crf,'-preset','fast','-bf','0','-x264-params','open-gop=0','-video_track_timescale',fps.numerator,out],f'Video {i+1}/{len(t.clips)}',base,span*.85,dur)
                    v=core.probe(out,'-select_streams','v:0','-show_entries','stream=nb_frames')['streams'][0]
                    if int(v['nb_frames'])!=n: raise ValueError('Unexpected frame count')
                    parts.append(out)
                # Sample counts use global rounded boundaries to prevent cumulative drift.
                count=round(Fraction(elapsed+n,1)/fps*48000)-round(Fraction(elapsed,1)/fps*48000)
                raw=p/'segment.raw'
                if c.mute or not s['audio']:
                    remaining=count*4
                    while remaining:
                        block=min(remaining,262144); audio.write(bytes(block)); remaining-=block
                else:
                    af=f'aresample=48000,atrim=start_sample={round(Fraction(c.start,1)/fps*48000)}:end_sample={round(Fraction(c.end,1)/fps*48000)},asetpts=PTS-STARTPTS,apad'
                    run(['-i',c.source,'-map','0:a:0','-vn','-af',af,'-ac',2,'-ar',48000,'-t',f'{count/48000:.12f}','-f','s16le',raw],f'Audio {i+1}/{len(t.clips)}',base+span*.85,span*.15,dur)
                    if raw.stat().st_size!=count*4: raise ValueError('Unexpected audio sample count')
                    with raw.open('rb') as f:
                        import shutil
                        shutil.copyfileobj(f,audio)
                    raw.unlink()
                elapsed+=n
        lst=p/'list.txt'; lst.write_text(''.join(f"file '{x.name}'\n" for x in parts))
        result=p/'result.mp4'
        video_input=['-i',smart_video] if mode=='smart' else ['-f','concat','-safe','1','-i',lst]
        run([*video_input,'-f','s16le','-ar',48000,'-ac',2,'-i',pcm,'-map','0:v:0','-map','1:a:0','-c:v','copy',*(['-tag:v','avc3'] if mode=='smart' else []),'-c:a','aac','-b:a','192k','-map_metadata','-1','-map_chapters','-1','-movflags','+faststart',result],'Mux',90,8,seconds)
        v=core.probe(result,'-select_streams','v:0','-show_entries','stream=nb_frames')['streams'][0]
        if int(v['nb_frames'])!=total: raise ValueError('Final frame count mismatch')
        if mode=='smart':
            from smart_engine import verify
            verify(result,fps,expected)
        # No overwrite, even if destination appeared during export.
        # Android shared storage may not support hardlinks. Reserve the name exclusively.
        import shutil
        with dst.open('xb') as output:
            try:
                with result.open('rb') as inp: shutil.copyfileobj(inp,output)
            except BaseException:
                output.close()
                dst.unlink(missing_ok=True)
                raise
    emit(progress=100,stage='Done')

def cancel(sig,frame):
    raise KeyboardInterrupt

if __name__=='__main__':
    signal.signal(signal.SIGTERM,cancel)
    try: render(json.loads(sys.argv[1]))
    except KeyboardInterrupt: print('Cancelled',flush=True); sys.exit(130)
    except Exception as e: print('ERROR:',e,flush=True); sys.exit(1)
