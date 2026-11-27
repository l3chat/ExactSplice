# ExactSplice

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Українська](README.uk.md)

**Frame-accurate video editing with minimal re-encoding.**

ExactSplice is an open-source, local FFmpeg-based video editor, originally developed as Video Hide for redacting confidential portions of recordings. The browser interface runs on the same device as the Python server; no cloud service is required.

## Status

The reference release is [Video Hide v0.3.1](https://github.com/l3chat/ExactSplice/releases/tag/v0.3.1). The broader editor (0.4) is under development. Portable Windows, Linux and macOS bundles are planned, not yet available.

## Installation

On Android, install Termux and run the following commands. On Linux, install Python 3 and FFmpeg (including ffprobe, libx264 and drawtext), then clone the repository and launch the server.

### Android / Termux

```sh
pkg install python ffmpeg git
termux-setup-storage
git clone --branch v0.3.1 https://github.com/l3chat/ExactSplice.git
cd ExactSplice
python gui.py
```

### Linux

```sh
git clone --branch v0.3.1 https://github.com/l3chat/ExactSplice.git
cd ExactSplice
python3 gui.py /path/to/videos
```

Open http://127.0.0.1:8765 in your browser. The legacy interface is currently in Russian. Use a local media directory as the optional command-line argument.

## Workflow

1. Select a source video; browser playback depends on codec support.
2. Scan for keyframes when using Smart modes. Use the zoomable timeline, keyframe navigation and frame-step controls to set the beginning and end of each interval.
3. Add each interval. Overlapping or adjacent intervals are merged; a valid unfinished selection is also included in export.
4. Set background colour, timer colour and size, and enable preview. The exported mask contains the countdown, not the preview label.
5. Save or reopen the JSON project; it contains paths and settings, not video data. Version 0.2 projects can be loaded; select Smart Exact manually if needed.
6. Choose export mode, audio handling, CRF and a new MP4 filename. Monitor the progress and log; keep the server running until completion.

## Export modes

- **Full:** encodes the entire video to H.264; default CRF 18.
- **Smart:** expands redaction intervals outward to existing keyframes and copies unaffected GOPs without re-encoding.
- **Smart Exact (experimental):** re-encodes affected GOPs only, masks by frame number and creates IDR frames at internal redaction boundaries. Unaffected GOPs are copied. Boundaries between frames are rounded up to the next presentation frame; the timer counts down to the actual end of masking.

## Compatibility and privacy

Smart modes require ordinary H.264, yuv420p, constant frame rate (CFR), square pixels and zero video start time, with suitable interior keyframes on both sides of the intervals. Use Full otherwise. Packet counts, presentation timestamps and decoded frames around joins are checked; failures prevent publication. Optional full frame verification compares decoded output against prepared segments; in Full mode it only checks decoding. These checks do not guarantee confidentiality: review every hidden interval and listen to the output before sharing.

Only the first audio track is retained. Muting re-encodes it to AAC with a 0.25 s margin on both sides; verify the result. Subtitles, chapters and source metadata are not copied. Source files remain unchanged. Output size is not guaranteed; estimates ignore bitrate variation and new data.

## Progress and cancellation

The progress display is approximate and includes the current stage, FFmpeg speed, elapsed time, estimated remaining time and current operation size when available. Keyframe scanning has no exact percentage. Cancel using the Stop button; the server sends SIGTERM to the process group and normally cleans up temporary files without publishing output. Forced termination can leave .video-hide-* directories beside the output; they may contain confidential source frames. Remove them only after processing stops.

## Testing and DTS fix

Version 0.3.1 normalizes decoding timestamps (DTS) across segments while preserving presentation timestamps (PTS). Synthetic Linux tests reported success with zero, one and two B-frames, including Smart Exact verification and cancellation. A user also reported successful processing of a long Zoom recording on Android. Broad device, codec and audio-redaction validation remains incomplete.

## License

See [LICENSE](LICENSE). FFmpeg and other dependencies have their own licenses.
