"""Basic final audio timing verification (not a privacy or content proof)."""
from fractions import Fraction
import video_hide as core

def verify_audio(path, frames, fps):
    streams=core.probe(path,"-show_streams")["streams"]
    tracks=[s for s in streams if s["codec_type"]=="audio"]
    if len(tracks)!=1: raise ValueError("Expected exactly one audio track")
    a=tracks[0]; rate=int(a["sample_rate"])
    if rate!=48000 or int(a["channels"])!=2: raise ValueError("Unexpected audio format")
    tb=Fraction(a["time_base"])
    start=int(a["start_pts"])*tb
    duration=int(a["duration_ts"])*tb
    expected=Fraction(frames)/fps
    # MP4 track duration may be rounded to the movie timescale; AAC has
    # encoder priming and tail padding. This is a timing sanity check.
    if abs(start)>Fraction(1,1000) or abs(duration-expected)>Fraction(1024,rate)+Fraction(1,1000):
        raise ValueError("Audio track timing mismatch")
    return {"sample_rate":rate,"duration":float(duration),"expected":float(expected)}
