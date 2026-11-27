import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from timeline import Timeline, Clip
from render_timeline import source_info
from smart_engine import render_video,frame_hashes,verify

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
class SmartTests(unittest.TestCase):
    def test_copy_reorder(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); src=p/"src.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=size=160x120:rate=25","-frames:v","75","-c:v","libx264","-pix_fmt","yuv420p","-g","25","-keyint_min","25","-sc_threshold","0","-bf","2","-x264-params","open-gop=0",str(src)],check=True)
            name=str(src); original=frame_hashes(src)
            t=Timeline(25,[Clip(name,50,75),Clip(name,0,25)])
            out,expected=render_video(t,{name:source_info(src)},p,18)
            self.assertEqual(expected,original[50:75]+original[:25])
            verify(out,Fraction(25),expected)

    def test_partial_gop(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); src=p/"src.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=size=160x120:rate=25","-frames:v","75","-c:v","libx264","-pix_fmt","yuv420p","-g","25","-keyint_min","25","-sc_threshold","0","-bf","2","-x264-params","open-gop=0",str(src)],check=True)
            name=str(src); original=frame_hashes(src)
            t=Timeline(25,[Clip(name,10,65)])
            out,expected=render_video(t,{name:source_info(src)},p,18)
            self.assertEqual(len(expected),55)
            self.assertEqual(expected[15:40],original[25:50])
            verify(out,Fraction(25),expected)

    def test_overlapping_and_repeated_copy_cache(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); src=p/"src.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=size=160x120:rate=25","-frames:v","100","-c:v","libx264","-pix_fmt","yuv420p","-g","25","-keyint_min","25","-sc_threshold","0","-bf","2","-x264-params","open-gop=0",str(src)],check=True)
            name=str(src); original=frame_hashes(src)
            t=Timeline(25,[Clip(name,0,75),Clip(name,25,100),Clip(name,25,50)])
            events=[]
            out,expected=render_video(t,{name:source_info(src)},p,18,lambda **kw: events.append(kw))
            self.assertEqual(expected,original[:75]+original[25:100]+original[25:50])
            verify(out,Fraction(25),expected)
            metrics=events[-1]["metrics"]
            self.assertEqual(metrics["source_splits"],1)
            self.assertEqual(metrics["unique_copy_segments"],4)
            self.assertTrue(src.exists())
            self.assertFalse(list(p.glob("cache*/*.mp4")))
