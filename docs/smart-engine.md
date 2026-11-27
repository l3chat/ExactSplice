# Smart Exact engine (experimental)

Select Smart Exact in the development editor, or pass mode=smart to the
timeline renderer. Full remains the default. The engine proposes COPY
ranges from structural IDR candidates, independently decodes extracted
ranges and compares every frame with the original. Other ranges are encoded
or generated. Concatenation normalizes DTS and the final video is checked
against every prepared frame and the integer presentation grid, including
after audio muxing. There is no silent fallback to Full.

The initial implementation favors verification over speed: it decodes
source video to compute hashes, splits source files for each COPY range,
and stores packet metadata and hashes. This is not yet optimized for long
recordings or low storage. The avc3 output permits in-band parameter sets;
player compatibility and mixed configurations require more validation.
Audio is still re-encoded using the existing PCM timeline; audio content
and synchronization are not yet independently verified. Same FPS only.
Do not rely on this alpha for confidential media without reviewing output.

Tests cover reordered copied GOPs and mixed partial-GOP encoding. Passing
unit tests is not evidence of support for arbitrary real recordings.
