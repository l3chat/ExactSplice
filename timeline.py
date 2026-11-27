"""Non-destructive single-track edit model. All positions are integer project frames.
Source offsets are also project-frame units; mixed-rate media needs normalization
before rendering. Intervals are half-open [start, end).
"""
from dataclasses import dataclass, replace, asdict
from fractions import Fraction

@dataclass(frozen=True)
class Clip:
    source: str
    start: int
    end: int
    hidden: bool = False
    mute: bool = False

    def __post_init__(self):
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("Source required")
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start < self.end:
            raise ValueError("Invalid source frame interval")
        if type(self.hidden) is not bool or type(self.mute) is not bool:
            raise ValueError("Invalid clip flags")

    @property
    def length(self):
        return self.end - self.start

    def slice(self, a, b):
        return replace(self, start=self.start+a, end=self.start+b)

def duration(clips):
    return sum(c.length for c in clips)

def partition(clips, position):
    if type(position) is not int or not 0 <= position <= duration(clips):
        raise ValueError("Position outside timeline")
    left, right = [], []
    for c in clips:
        n = min(position, c.length)
        if n: left.append(c.slice(0,n))
        if n < c.length: right.append(c.slice(n,c.length))
        position -= n
    return tuple(left), tuple(right)

class Timeline:
    def __init__(self, fps, clips=()):
        self.fps = Fraction(fps)
        if self.fps <= 0: raise ValueError("Invalid frame rate")
        self.clips = tuple(clips)
        if not all(isinstance(c, Clip) for c in self.clips): raise ValueError("Invalid clips")
        self._undo, self._redo = [], []

    @property
    def length(self):
        return duration(self.clips)

    def _change(self, clips):
        clips = tuple(clips)
        if clips != self.clips:
            self._undo.append(self.clips)
            self.clips = clips
            self._redo.clear()

    def _range(self,a,b):
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= self.length:
            raise ValueError("Invalid timeline selection")
        left, rest = partition(self.clips,a)
        middle, right = partition(rest,b-a)
        return left,middle,right

    def copy(self,a,b):
        return self._range(a,b)[1]

    def cut(self,a,b):
        left,middle,right = self._range(a,b)
        self._change(left+right)
        return middle

    def delete(self,a,b):
        self.cut(a,b)

    def insert(self,position,clips):
        clips = tuple(clips)
        if not all(isinstance(c,Clip) for c in clips): raise ValueError("Invalid clips")
        left,right = partition(self.clips,position)
        self._change(left+clips+right)

    paste = insert

    def move(self,a,b,destination):
        """Destination is measured BEFORE removal. Inside selection: no-op."""
        left,middle,right = self._range(a,b)
        if type(destination) is not int or not 0 <= destination <= self.length:
            raise ValueError("Invalid destination")
        if a <= destination <= b: return
        if destination > b: destination -= b-a
        x,y = partition(left+right,destination)
        self._change(x+middle+y)

    def replace(self,a,b,clips):
        left,_,right = self._range(a,b)
        clips=tuple(clips)
        if not all(isinstance(c,Clip) for c in clips): raise ValueError("Invalid clips")
        self._change(left+clips+right)

    def hide(self,a,b,mute=True):
        left,middle,right = self._range(a,b)
        self._change(left+tuple(replace(c,hidden=True,mute=mute) for c in middle)+right)

    def split(self,position):
        left,right = partition(self.clips,position)
        self._change(left+right)

    def undo(self):
        if not self._undo: return False
        self._redo.append(self.clips)
        self.clips=self._undo.pop()
        return True

    def redo(self):
        if not self._redo: return False
        self._undo.append(self.clips)
        self.clips=self._redo.pop()
        return True

    def to_dict(self):
        return {"schema":1,"fps":str(self.fps),"timeline":[asdict(c) for c in self.clips]}

    @classmethod
    def from_dict(cls,data):
        if data.get("schema") != 1: raise ValueError("Unsupported project schema")
        return cls(data["fps"],[Clip(**c) for c in data["timeline"]])

    @classmethod
    def from_legacy(cls,data,fps,frame_count):
        """Import old Video Hide project; ceil boundaries onto presentation grid."""
        from math import ceil
        rate=Fraction(fps)
        t=cls(rate,[Clip(data["file"],0,frame_count)])
        for a,b in data["intervals"]:
            if not 0 <= Fraction(str(a)) < Fraction(str(b)) <= Fraction(frame_count)/rate:
                raise ValueError("Legacy interval outside source")
            l,r=ceil(Fraction(str(a))*rate),ceil(Fraction(str(b))*rate)
            if l<r: t.hide(l,r,bool(data.get("mute",False)))
        t._undo.clear()
        return t
