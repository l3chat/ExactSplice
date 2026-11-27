"""Conservative, pure export planning on the project frame grid.

COPY means a candidate for packet copying, not a verified splice. Only
independently verified closed-GOP boundaries and matching stream signatures
may be supplied by the future media inspector.
"""
from dataclasses import dataclass
from fractions import Fraction
from bisect import bisect_left, bisect_right
from collections import Counter

@dataclass(frozen=True)
class Source:
    frames: int
    fps: Fraction
    width: int
    height: int
    signature: str | None = None
    safe_boundaries: tuple[int, ...] = ()

    def __post_init__(self):
        if type(self.frames) is not int or self.frames <= 0:
            raise ValueError("Invalid source length")
        if Fraction(self.fps) <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("Invalid source format")
        k = self.safe_boundaries
        if any(type(x) is not int or not 0 <= x <= self.frames for x in k):
            raise ValueError("Invalid GOP boundary")
        if tuple(sorted(set(k))) != k:
            raise ValueError("GOP boundaries must be sorted and unique")

@dataclass(frozen=True)
class Part:
    action: str
    source: str
    start: int
    end: int
    output_start: int
    mute: bool
    reason: str

    @property
    def frames(self):
        return self.end - self.start

def plan(timeline, sources, *, output_signature=None, dimensions=None):
    """Return ordered, exhaustive, nonoverlapping output parts.

    No changes to source files. No inferred safe boundaries from ordinary
    keyframe flags. Different FPS is rejected until the timeline supports
    an explicit source-to-project frame mapping.
    """
    if not timeline.clips:
        raise ValueError("Empty timeline")
    first = sources[timeline.clips[0].source]
    dimensions = dimensions or (first.width, first.height)
    result = []
    offset = 0
    for clip in timeline.clips:
        s = sources[clip.source]
        if Fraction(s.fps) != timeline.fps:
            raise ValueError("Mixed FPS requires explicit frame mapping")
        if clip.end > s.frames:
            raise ValueError("Source interval exceeds source length")

        def add(action, a, b, reason):
            nonlocal offset
            if a < b:
                result.append(Part(action, clip.source, a, b, offset, clip.mute, reason))
                offset += b-a

        a,b = clip.start,clip.end
        if clip.hidden:
            add("GENERATE", a,b,"Independent mask; no source video pixels")
        elif (s.width,s.height) != dimensions:
            add("CONVERT",a,b,"Resolution differs from project")
        elif not output_signature or s.signature != output_signature:
            add("ENCODE",a,b,"Stream compatibility not established")
        else:
            k=s.safe_boundaries
            i=bisect_left(k,a)
            j=bisect_right(k,b)-1
            if i >= len(k) or j < i or k[i] >= k[j]:
                add("ENCODE",a,b,"No complete independently verified GOP")
            else:
                add("ENCODE",a,k[i],"Leading partial GOP")
                add("COPY",k[i],k[j],"Verified GOP boundaries; compatible stream")
                add("ENCODE",k[j],b,"Trailing partial GOP")
    if offset != timeline.length:
        raise AssertionError("Plan duration mismatch")
    return tuple(result)

def statistics(parts):
    counts=Counter()
    for p in parts:
        counts[p.action]+=p.frames
    return {k:counts[k] for k in ("COPY","ENCODE","GENERATE","CONVERT")}
