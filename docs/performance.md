# Smart Exact performance (development)

The COPY cache groups requested source intervals by file. Each file is split
at the union of requested interior IDR boundaries once per export. Unused
pieces are removed immediately, overlapping requests reuse elementary
segments, and repeated elementary segments reuse the same independently
verified remux. The source is never modified.

Status metrics include source_splits, peak_single_split_bytes (only the
largest single split operation, not whole-job peak disk usage),
retained_cache_bytes (sum after initial cache preparation),
unique_copy_segments, prepared_video_bytes and video_seconds (elapsed wall
time for video processing, not audio). These are measured, not predicted.

Full decoded-frame checks remain mandatory. No fast verification option is
enabled yet. Source hashing and encoding partial GOPs still require decoding,
and the audio renderer still reads source audio separately for each clip.
Peak total storage and RSS are not measured by these metrics.
