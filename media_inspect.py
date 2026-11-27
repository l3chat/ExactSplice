"""Conservative H.264/MP4 packet inspector for Smart Exact.

Structural IDR candidates are not independently decode-verified boundaries.
The default planner source therefore exposes no COPY boundaries.
"""
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from export_plan import Source

def unhex_dump(dump):
    result=bytearray()
    for line in dump.splitlines():
        if not line.strip(): continue
        m=re.fullmatch(r"\s*([0-9a-fA-F]+):\s*(.*?)\s{2,}.*",line)
        if not m: raise ValueError("Invalid ffprobe hex dump")
        if int(m[1],16)!=len(result): raise ValueError("Invalid hex offset")
        result.extend(bytes.fromhex(m[2]))
    return bytes(result)

def nal_length_size(avcc):
    if len(avcc)<7 or avcc[0]!=1 or (avcc[4]&252)!=252:
        raise ValueError("Invalid AVC configuration")
    n=(avcc[4]&3)+1
    if n not in (1,2,4): raise ValueError("Unsupported NAL length size")
    return n

def nal_types(data,n):
    if n not in (1,2,4): raise ValueError("Invalid NAL length size")
    i=0; result=[]
    while i<len(data):
        if i+n>len(data): raise ValueError("Truncated NAL length")
        size=int.from_bytes(data[i:i+n],"big"); i+=n
        if size<1 or i+size>len(data): raise ValueError("Invalid NAL size")
        if data[i]&128: raise ValueError("Invalid NAL header")
        result.append(data[i]&31); i+=size
    if not result: raise ValueError("Empty packet")
    return tuple(result)

def is_idr(data,n):
    kinds=nal_types(data,n)
    # Reject mixed VCL types, in-band parameter changes and unsupported extensions.
    return 5 in kinds and all(k in (5,6,9,10,11,12) for k in kinds)

def packet_grid(packets, frames, step):
    """Return structural candidate frame indices after validating decode groups.

    packets: iterable of (PTS in ticks, DTS in ticks, IDR candidate).
    Each group bounded by IDRs must contain exactly its presentation range.
    """
    if frames<=0 or step<=0: raise ValueError("Invalid grid")
    seen=bytearray(frames); group_min=None; group_max=None; group_count=0
    starts=[]; previous_dts=None; count=0
    for pts,dts,idr in packets:
        if pts%step: raise ValueError("PTS outside CFR grid")
        f=pts//step
        if not 0<=f<frames or seen[f]: raise ValueError("Missing or duplicate presentation frame")
        if previous_dts is not None and dts<=previous_dts: raise ValueError("Non-monotonic DTS")
        previous_dts=dts; seen[f]=1; count+=1
        if idr:
            if group_count and (group_min!=starts[-1] or group_max!=f-1 or group_count!=f-starts[-1]):
                raise ValueError("Presentation frames cross IDR boundary")
            if not starts and f!=0: raise ValueError("First IDR is not frame zero")
            starts.append(f); group_min=group_max=f; group_count=1
        elif not starts:
            raise ValueError("First packet is not independently decodable IDR")
        else:
            group_min=min(group_min,f); group_max=max(group_max,f); group_count+=1
    if count!=frames or not starts or group_min!=starts[-1] or group_max!=frames-1 or group_count!=frames-starts[-1]:
        raise ValueError("Incomplete presentation grid")
    return tuple(starts+[frames])

@dataclass(frozen=True)
class Inspection:
    source: Source
    candidates: tuple[int,...]

def inspect(path):
    path=Path(path).resolve()
    meta=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_streams","-show_format","-show_data","-of","json",str(path)]))
    v=meta["streams"][0]
    if "mov" not in meta["format"]["format_name"].split(",") or v.get("codec_name")!="h264" or v.get("codec_tag_string")!="avc1":
        raise ValueError("Only H.264 avc1 in MP4/MOV supported")
    if v.get("pix_fmt")!="yuv420p" or v.get("sample_aspect_ratio","1:1") not in ("1:1","0:1") or v.get("side_data_list"):
        raise ValueError("Unsupported pixel format, aspect ratio or side data")
    fps=Fraction(v["avg_frame_rate"]); tb=Fraction(v["time_base"])
    if fps<=0 or fps!=Fraction(v["r_frame_rate"]) or int(v.get("start_pts",0))!=0:
        raise ValueError("Only zero-start CFR supported")
    step=1/fps/tb
    if step.denominator!=1: raise ValueError("Nonintegral frame grid")
    frames=int(v["nb_frames"])
    if not 0<frames<=100_000_000: raise ValueError("Unsupported frame count")
    avcc=unhex_dump(v["extradata"]); n=nal_length_size(avcc)
    fields=("codec_name","codec_tag_string","profile","level","width","height","pix_fmt","sample_aspect_ratio","field_order","color_range","color_space","color_transfer","color_primaries","chroma_location","time_base","avg_frame_rate")
    signature=hashlib.sha256(json.dumps({k:v.get(k) for k in fields},sort_keys=True).encode()+avcc).hexdigest()
    cmd=["ffprobe","-v","error","-select_streams","v:0","-show_packets","-show_entries","packet=pts,dts,pos,size,flags","-of","compact=p=0:nk=0",str(path)]
    size=path.stat().st_size
    with path.open("rb") as f:
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,text=True)
        def packets():
            for line in p.stdout:
                if not line.strip(): continue
                d=dict(x.split("=",1) for x in line.strip().split("|") if "=" in x)
                if "pts" not in d: raise ValueError("Unexpected packet metadata")
                flags=d["flags"]
                if "D" in flags or "C" in flags: raise ValueError("Discarded or corrupt packet")
                idr=False
                if "K" in flags:
                    pos,length=int(d["pos"]),int(d["size"])
                    if not 0<=pos<size or not 0<length<=min(size-pos,64*1024*1024): raise ValueError("Invalid packet position")
                    f.seek(pos); data=f.read(length)
                    if len(data)!=length: raise ValueError("Truncated packet")
                    idr=is_idr(data,n)
                yield int(d["pts"]),int(d["dts"]),idr
        try:
            candidates=packet_grid(packets(),frames,int(step))
            if p.wait(): raise ValueError("Packet inspection failed")
        finally:
            if p.poll() is None: p.terminate(); p.wait()
    return Inspection(Source(frames,fps,v["width"],v["height"],signature,()),candidates)

if __name__=="__main__":
    import sys
    from dataclasses import asdict
    result=inspect(sys.argv[1])
    print(json.dumps(asdict(result),default=str,indent=2))
