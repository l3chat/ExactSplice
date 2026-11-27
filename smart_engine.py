"""Experimental verified hybrid H.264 exporter.

Structural IDR candidates only propose ranges. Actual copied ranges are
accepted only after independent decoding matches the original frames.
Every final decoded frame and presentation timestamp is checked.
"""
import subprocess
import json
import time
from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from export_plan import Source, plan, statistics
from media_inspect import inspect
import video_hide as core

def ff(args):
    subprocess.run(["ffmpeg","-v","error","-xerror","-nostdin","-y",*map(str,args)],check=True)

def frame_hashes(path, start=None, end=None):
    args=["ffmpeg","-v","error","-xerror","-nostdin","-i",str(path),"-map","0:v:0","-an"]
    if start is not None:
        args+=["-vf",f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS"]
    args+=["-fps_mode","passthrough","-pix_fmt","yuv420p","-f","framemd5","-"]
    raw=subprocess.check_output(args,text=True)
    return [line.rsplit(",",1)[-1].strip() for line in raw.splitlines() if line and not line.startswith("#")]

def grid(path,fps,expected):
    meta=core.probe(path,"-select_streams","v:0","-show_streams")["streams"][0]
    tb=Fraction(meta["time_base"]); step=1/fps/tb
    if step.denominator!=1: raise ValueError("Output time base cannot represent frame grid")
    step=int(step)
    d=core.probe(path,"-select_streams","v:0","-show_packets","-show_entries","packet=pts,dts,flags")
    seen=bytearray(expected); delay=0; last=None
    for i,p in enumerate(d["packets"]):
        pts,dts=int(p["pts"]),int(p["dts"])
        if pts%step or not 0<=pts//step<expected or seen[pts//step]:
            raise ValueError("Missing, duplicate or off-grid output PTS")
        if "D" in p.get("flags","") or "C" in p.get("flags",""):
            raise ValueError("Discarded or corrupt output packet")
        if last is not None and dts<=last: raise ValueError("Nonmonotonic output DTS")
        seen[pts//step]=1;last=dts
        delay=max(delay,i-pts//step)
    if len(d["packets"])!=expected or not all(seen):
        raise ValueError("Output packet count mismatch")
    return delay

def verify(path,fps,expected_hashes):
    grid(path,fps,len(expected_hashes))
    if frame_hashes(path)!=expected_hashes:
        raise ValueError("Decoded output does not match prepared segments")

def prepare_copy_cache(parts, models, fps, folder, emit):
    """Split each source at most once, retain only requested ranges.

    Overlapping selections are represented by shared elementary segments.
    A requested range may contain several elementary segments; each is
    independently remuxed and verified later before joining.
    """
    requests=defaultdict(set)
    for part in parts:
        if part.action=="COPY": requests[part.source].add((part.start,part.end))
    cache={}; splits=0; peak_split_bytes=0; retained_bytes=0
    for i,(source,ranges) in enumerate(requests.items()):
        frames=models[source].frames
        bounds=sorted({0,frames}|{x for ab in ranges for x in ab})
        cuts=bounds[1:-1]
        if not cuts:
            cache[source]={(0,frames):Path(source)}
            continue
        sub=folder/f"cache{i:05d}";sub.mkdir()
        emit(stage=f"Smart Exact: split source {i+1}/{len(requests)}",progress=0)
        ff(["-i",source,"-map","0:v:0","-an","-c:v","copy","-f","segment",
            "-segment_times",",".join(f"{float(Fraction(x)/fps):.9f}" for x in cuts),
            "-segment_time_delta","0.000001","-reset_timestamps","1",sub/"g%06d.mp4"])
        segments=sorted(sub.glob("g*.mp4"));splits+=1
        if len(segments)!=len(bounds)-1: raise ValueError("Unexpected cached GOP segment count")
        peak_split_bytes=max(peak_split_bytes,sum(x.stat().st_size for x in segments))
        cache[source]={}
        for a,b,path in zip(bounds,bounds[1:],segments):
            if any(l<=a and b<=r for l,r in ranges):
                cache[source][a,b]=path
                retained_bytes+=path.stat().st_size
            else: path.unlink()
    return cache,{"source_splits":splits,"peak_single_split_bytes":peak_split_bytes,"retained_cache_bytes":retained_bytes}

def expand_copy_parts(parts,cache):
    """Expand overlapping COPY selections on shared verified boundaries."""
    result=[]
    for part in parts:
        if part.action!="COPY":
            result.append(part);continue
        ranges=sorted((a,b) for a,b in cache[part.source] if part.start<=a and b<=part.end)
        cursor=part.start
        for a,b in ranges:
            if a!=cursor: raise ValueError("COPY cache coverage gap")
            result.append(replace(part,start=a,end=b,output_start=part.output_start+a-part.start))
            cursor=b
        if cursor!=part.end: raise ValueError("COPY cache coverage mismatch")
    return result

def render_video(t,sources,folder,crf,emit=lambda **kw:None):
    """Create video-only MP4. Audio is handled by the timeline renderer."""
    started=time.monotonic()
    p=Path(folder); fps=t.fps; first=sources[t.clips[0].source]; w,h=first["width"],first["height"]
    models={}; signature=None; original={}; inspected={}
    for name,s in sources.items():
        if not any(c.source==name and not c.hidden for c in t.clips):
            models[name]=Source(s["frames"],fps,s["width"],s["height"])
            continue
        try:
            info=inspect(name)
        except (ValueError,KeyError,IndexError,subprocess.CalledProcessError):
            models[name]=Source(s["frames"],fps,s["width"],s["height"])
            continue
        inspected[name]=info
        if signature is None and (s["width"],s["height"])==(w,h):
            signature=info.source.signature
        # These are tentative candidates, not a safety proof. The executor below
        # independently validates every proposed COPY range before accepting it.
        models[name]=replace(info.source,safe_boundaries=info.candidates)
    parts=plan(t,models,output_signature=signature,dimensions=(w,h))
    stats=statistics(parts); emit(stage="Smart Exact: proposed plan",progress=0,plan=stats)
    cache,metrics=prepare_copy_cache(parts,models,fps,p,emit)
    parts=expand_copy_parts(parts,cache)
    prepared={}
    paths=[]; expected=[]; delays=[]; timescale=fps.numerator
    for i,part in enumerate(parts):
        n=part.frames; dur=float(Fraction(n)/fps); out=p/f"smart{i:05d}.mp4"
        emit(stage=f"{part.action} {i+1}/{len(parts)}",progress=50*part.output_start/t.length)
        if part.action=="COPY":
            # Seek only to a structurally identified IDR. Do not trust -t or
            # container frame counts: independent decoding and PTS checks below
            # reject extra/missing packets, preroll or incorrect seeks.
            if part.source not in original:
                original[part.source]=frame_hashes(part.source)
                if len(original[part.source])!=models[part.source].frames:
                    raise ValueError("Source decoded frame count mismatch")
            key=(part.source,part.start,part.end)
            if key in prepared:
                cached,hashes,delay=prepared[key]
                paths.append(cached);expected.extend(hashes);delays.append(delay)
                continue
            src=cache[part.source][part.start,part.end]
            ff(["-i",src,"-map","0:v:0","-an","-c:v","copy","-video_track_timescale",timescale,"-map_metadata","-1","-map_chapters","-1",out])
            hashes=original[part.source][part.start:part.end]
            if frame_hashes(out)!=hashes:
                raise ValueError("Independent COPY verification failed; use Full explicitly")
        else:
            if part.action=="GENERATE":
                args=["-f","lavfi","-i",f"color=c=0xd9d9d9:s={w}x{h}:r={fps}"]
                vf=core.timer(dur,core.fontpath())
            else:
                args=["-i",part.source]
                vf=f"trim=start_frame={part.start}:end_frame={part.end},settb=expr={1/fps},setpts=N,scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            ff([*args,"-map","0:v:0","-an","-vf",vf,"-frames:v",n,"-r",str(fps),"-fps_mode","cfr","-c:v","libx264","-pix_fmt","yuv420p","-crf",crf,"-preset","fast","-bf","0","-x264-params","open-gop=0","-video_track_timescale",timescale,out])
            hashes=frame_hashes(out)
        if len(hashes)!=n: raise ValueError("Prepared frame count mismatch")
        delay=grid(out,fps,n)
        delays.append(delay); paths.append(out);expected.extend(hashes)
        if part.action=='COPY': prepared[key]=(out,hashes,delay)
    for name,mapping in cache.items():
        for path in mapping.values():
            if path != Path(name): path.unlink()
    # Explicit durations plus a shared decode delay maintain CFR presentation
    # order even when source and newly encoded parts use different B-frame depths.
    lst=p/"smart-concat.txt"
    lst.write_text("".join(f"file '{x.name}'\nduration {float(Fraction(part.frames)/fps):.12f}\n" for x,part in zip(paths,parts)))
    delay=max(delays);step=fps.denominator
    bsf=f"setts=pts=PTS:dts=(N-{delay})*{step}:duration={step}"
    out=p/"smart-video.mp4"
    emit(stage="Smart Exact: concatenate and verify",progress=52)
    # concat auto-conversion inserts H.264 parameter sets at segment starts.
    # avc3 explicitly permits in-band parameter sets. Decoded verification
    # rejects incompatible configurations rather than silently publishing them.
    ff(["-f","concat","-safe","1","-auto_convert","1","-i",lst,"-map","0:v:0","-an","-c:v","copy","-bsf:v",bsf,"-tag:v","avc3","-video_track_timescale",timescale,out])
    verify(out,fps,expected)
    metrics.update(video_seconds=round(time.monotonic()-started,3),unique_copy_segments=len(prepared),prepared_video_bytes=sum(x.stat().st_size for x in set(paths)))
    emit(stage="Smart Exact: video verified",progress=60,plan=stats,metrics=metrics)
    return out,expected
