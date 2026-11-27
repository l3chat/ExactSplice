# Development editor (0.4 alpha)

Run the existing server: python gui.py /path/to/videos (or python gui.py on Termux).
Open http://127.0.0.1:8765/editor. The original redaction editor is still at /.

Select source; create project; use integer frame ranges and destination. Copy,
cut, paste, delete, move, replace, split, hide, external insert and undo/redo
are supported through the timeline model. Clicking a clip previews its source,
not the continuous final timeline. Hidden clips are masked in preview; do not
treat browser preview as a confidentiality guarantee.

The experimental renderer explicitly uses Full encode: every video clip is
encoded to H.264 and audio is resampled to 48 kHz stereo then encoded to AAC.
Only sources reporting the same constant frame rate, explicit frame counts,
zero start times and square pixels are accepted. The first remaining clip
defines resolution. Other sources are scaled and letterboxed. Hidden video is
generated independently; muted clips get zero PCM samples. Only first audio
track is exported. Countdown restarts at each hidden clip boundary. There is
no guarantee of exact audio synchronization until media tests have run.
Output frame counts are checked, but not full presentation timestamps.
Legacy JSON import preserves hide/mute ranges, not old style/export options.
Smart Exact for general edits is not implemented. Use the legacy editor for
production redaction. This alpha has not been tested on Android or real files.
