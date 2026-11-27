# Smart Exact export planner

Development milestone: pure planning, not a Smart Exact renderer.

The plan uses half-open integer frame intervals. Each output part has an
output offset, source interval, mute flag and reason.

- COPY: candidate for packet copy, only with matching verified stream
  signature and independently verified closed-GOP boundaries.
- ENCODE: partial GOP or unknown compatibility.
- GENERATE: independent redaction video, without source pixels.
- CONVERT: differing dimensions.

Ordinary keyframe flags are not proof of independent decoding. Neither EOF
nor frame zero is assumed safe unless explicitly supplied. The future media
inspector must verify boundaries and compatibility; the renderer must check
packet timestamps, decoded joins, frame counts and audio synchronization.
Mixed FPS remains unsupported until explicit frame mapping is implemented.

Example: at 25 fps, verified boundaries 0, 25, 50, 75, 100, a selection
[10,90) produces ENCODE [10,25), COPY [25,75), ENCODE [75,90).
No extra frames are included in the output.

The existing editor still uses Full export. No claim of lossless general
editing is made at this stage. Tests exercise the model independently.
