# H.264 media inspection

Run python media_inspect.py input.mp4 to inspect a source. The inspector
supports avc1 H.264 MP4/MOV, yuv420p, zero-start CFR and square pixels.
It hashes the AVC configuration and stream properties, checks packet PTS
coverage and monotonic DTS, parses length-prefixed NAL units in flagged
key packets, and checks that presentation ranges do not cross IDR groups.

The result lists structural candidates, including an EOF sentinel. They
are not yet independently decoded and are deliberately NOT passed to
the planner as safe COPY boundaries. A signature match alone is not proof
of safe concatenation. Future execution must independently verify decoded
ranges and output, including stream configuration and timestamps.

The inspector streams packet metadata and reads candidate payloads by file
offset; it does not load the complete video into memory. Unsupported or
ambiguous streams fail explicitly. Tests cover synthetic NAL packets,
reordered timestamps and a generated H.264 file with B-frames.
