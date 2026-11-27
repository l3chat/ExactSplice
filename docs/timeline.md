# ExactSplice 0.4 development: timeline model

This is an internal development milestone, not a finished editor.

The single-track timeline holds immutable references to source frame ranges.
All ranges are half-open. Edit coordinates refer to the current timeline,
except source offsets in clips. Move destinations are measured before removal.
Copy retains hide/mute flags, so copying a hidden clip does not uncover it.
Undo and redo restore the entire sequence atomically.

The model uses integer frame indices at a rational project frame rate.
Source offsets are measured on the project frame grid; external media with
different frame rates must be normalized or mapped explicitly by the future
renderer. No physical video editing is performed by this module.

Legacy import converts seconds to frame indices with ceiling, preserving
half-open selection semantics. It imports file and hide/mute ranges only.
Export settings and Smart expansion policies still require a separate
migration layer. The existing Video Hide GUI and renderer remain untouched.

Run model tests from the repository root:
    python -m unittest discover -s tests -v

Next milestones: GUI integration, source metadata validation, export planning,
safe GOP splicing and DTS normalization, audio synchronization, regression
tests with real FFmpeg media, and portable builds.
