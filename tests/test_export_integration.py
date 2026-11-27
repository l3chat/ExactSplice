"""End-to-end export regression tests using generated media only."""
import array
import contextlib
import io
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction
from timeline import Timeline,Clip
from render_timeline import render
from smart_engine import frame_hashes,grid
from audio_verify import verify_audio
import video_hide as core

def fixture(path, color, frequency, size="160x120", bf=2):
    subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i",f"color=c={color}:s={size}:r=25:d=3",
        "-f","lavfi","-i",f"sine=frequency={frequency}:sample_rate=48000:duration=3",
        "-map","0:v","-map","1:a","-c:v","libx264","-pix_fmt","yuv420p","-g","25","-keyint_min","25",
        "-sc_threshold","0","-bf",str(bf),"-x264-params","open-gop=0","-c:a","aac",str(path)],check=True)

def audio_samples(path):
    data=subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-map","0:a:0","-ac","1","-ar","48000","-f","s16le","-"])
    a=array.array("h"); a.frombytes(data)
    import sys
    if sys.byteorder!="little": a.byteswap()
    return a

def tone_strength(samples,start,end,freq):
    # A narrow frequency correlation, insensitive to phase.
    s=samples[round(start*48000):round(end*48000)]
    if not s: raise AssertionError("No decoded audio samples")
    x=sum(v*math.cos(2*math.pi*freq*i/48000) for i,v in enumerate(s))
    y=sum(v*math.sin(2*math.pi*freq*i/48000) for i,v in enumerate(s))
    return math.hypot(x,y)*2/len(s)

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name);self.a=self.p/"a.mp4";self.b=self.p/"b.mp4"
        fixture(self.a,"red",440);fixture(self.b,"blue",880)
    def export(self,clips,mode="smart",fps=25):
        dst=self.p/(mode+".mp4")
        t=Timeline(fps,clips)
        with contextlib.redirect_stdout(io.StringIO()):
            render({"project":t.to_dict(),"output":str(dst),"mode":mode,"crf":18})
        grid(dst,Fraction(fps),t.length)
        verify_audio(dst,t.length,Fraction(fps))
        return dst
    def test_external_copy_and_audio_order(self):
        a,b=str(self.a),str(self.b)
        dst=self.export([Clip(a,25,50),Clip(b,0,25),Clip(a,50,75)])
        self.assertEqual(frame_hashes(dst),frame_hashes(a)[25:50]+frame_hashes(b)[:25]+frame_hashes(a)[50:75])
        s=audio_samples(dst)
        for start,freq,other in [(0,440,880),(1,880,440),(2,440,880)]:
            self.assertGreater(tone_strength(s,start+.15,start+.85,freq),500)
            self.assertGreater(tone_strength(s,start+.15,start+.85,freq),10*tone_strength(s,start+.15,start+.85,other))
    def test_hidden_video_and_muted_audio(self):
        a=str(self.a)
        dst=self.export([Clip(a,0,25),Clip(a,25,50,True,True),Clip(a,50,75)])
        original=frame_hashes(a); output=frame_hashes(dst)
        self.assertEqual(output[:25],original[:25])
        self.assertEqual(output[50:],original[50:])
        self.assertTrue(set(output[25:50]).isdisjoint(original))
        # Independently check gray background at a corner away from countdown.
        raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(dst),"-vf","select=between(n\\,25\\,49),crop=2:2:0:0,format=rgb24","-fps_mode","passthrough","-f","rawvideo","-"])
        self.assertEqual(len(raw),25*12)
        self.assertTrue(all(205<=x<=230 for x in raw))
        samples=audio_samples(dst)
        self.assertLess(max(abs(v) for v in samples[round(1.15*48000):round(1.85*48000)]),100)
        self.assertGreater(tone_strength(samples,.15,.85,440),500)
        self.assertGreater(tone_strength(samples,2.15,2.85,440),500)
    def test_external_resolution_conversion(self):
        c=self.p/"wide.mp4";fixture(c,"green",660,"320x180",0)
        dst=self.export([Clip(str(self.a),0,25),Clip(str(c),0,25)])
        v=core.probe(dst,"-select_streams","v:0","-show_streams")["streams"][0]
        self.assertEqual((v["width"],v["height"]),(160,120))
        self.assertEqual(frame_hashes(dst)[:25],frame_hashes(self.a)[:25])
        s=audio_samples(dst);self.assertGreater(tone_strength(s,1.15,1.85,660),500)
    def test_full_export_audio(self):
        dst=self.export([Clip(str(self.a),10,35),Clip(str(self.b),25,50)],"full")
        s=audio_samples(dst)
        self.assertGreater(tone_strength(s,.15,.85,440),500)
        self.assertGreater(tone_strength(s,1.15,1.85,880),500)
    def test_reject_mixed_fps_without_output(self):
        dst=self.p/"bad.mp4"
        t=Timeline(30,[Clip(str(self.a),0,25)])
        with self.assertRaises(ValueError):
            render({"project":t.to_dict(),"output":str(dst),"mode":"smart"})
        self.assertFalse(dst.exists())
