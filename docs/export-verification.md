# End-to-end export verification

The new regression suite renders real MP4 files from generated sources with
distinct audio tones. It tests external insertion, copied video frame hashes,
masked video corner pixels, mute interiors, resolution conversion, Full export,
and rejection without publication for incompatible frame rates.

Final output now has an audio track timing sanity check: one 48 kHz stereo
track, near-zero start, duration within one AAC frame plus 1 ms of the
expected timeline. This does not establish sample-exact content alignment.
The tests independently correlate audio tones away from transitions; AAC
may smear audio at boundaries. Confidential audio must still be reviewed.
The legacy editor remains unchanged.

Temporary GOP split files are deleted after extraction rather than retained
until the end of the job. This reduces cumulative disk use but does not
eliminate repeated source scans or peak split storage. Further optimization,
cross-platform verification and GUI localization remain pending.
