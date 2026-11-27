import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from media_inspect import inspect

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
class MediaTests(unittest.TestCase):
    def test_closed_gop(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"source.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=size=160x120:rate=25","-frames:v","75","-c:v","libx264","-pix_fmt","yuv420p","-g","25","-keyint_min","25","-sc_threshold","0","-bf","2","-x264-params","open-gop=0",str(p)],check=True)
            result=inspect(p)
            self.assertEqual(result.candidates,(0,25,50,75))
            self.assertEqual(result.source.safe_boundaries,())
            self.assertEqual(result.source.frames,75)
            self.assertTrue(result.source.signature)
