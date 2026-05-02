# Testing Motion Background Studio (GUI)

This app is a Qt (PySide6) desktop GUI built into a single `.exe` for Windows via PyInstaller, but it runs identically on Linux for development testing.

## Launch the GUI for testing

```bash
cd /path/to/motion-bg-studio
DISPLAY=:0 uv run motion-bg-studio   # Linux X11; works in Devin's headed env
```

The entry point is registered in `pyproject.toml` as `motion-bg-studio = motion_bg_studio.app:main`.

## Where renders land

Default output folder: `~/MotionBackgrounds/`. Filenames are deterministic:
```
{style}_{palette}_{width}x{height}_{duration}s_{seed}.mp4
```
Use this naming pattern to glob for the file you just rendered:
```bash
ls ~/MotionBackgrounds/geometric_*_5s_9090.mp4
```

## Headless / CI

For unit tests that import PySide6, set `QT_QPA_PLATFORM=offscreen`. On GitHub Actions Ubuntu runners, also `apt-get install` the Qt runtime libs (already wired in `.github/workflows/test.yml`):
```
libegl1 libgl1 libxkbcommon0 libdbus-1-3
libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1
libxcb-xfixes0 libxcb-xkb1
```

## Adversarial recipe for FPS / resolution / duration changes

The encoded MP4 carries the ground truth, so do not trust UI labels alone. After a render, `ffprobe` it:

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames,duration \
  -of default=noprint_wrappers=1 \
  ~/MotionBackgrounds/<file>.mp4
```

Adversarial assertions for FPS testing: pick a non-preset value (e.g. 90 — the presets are `{24, 25, 30, 50, 60}`) and verify both `r_frame_rate=90/1` AND `nb_frames=duration*90`. A buggy implementation that ignored typed text and fell back to the preset/default would show `30/1` and `nb_frames=duration*30`. Both must match for the test to be meaningful.

Mid-render, the GUI status bar at the bottom of the window also shows `Job N/M: frame X/Y` — `Y` is the total frame count and is an independent witness.

## Maximize the window before recording

The GUI window does not auto-maximize. From the desktop, double-click the title bar, or:
```bash
DISPLAY=:0 xdotool search --name "Motion Background Studio" | head -1 | \
  xargs -I{} xdotool windowsize {} 100% 100% windowmove {} 0 0
```

## Smoke-test render time benchmarks

On the dev VM, expected render times for the recorded benchmarks:

| Spec | Style | Time |
|---|---|---|
| Full HD, 5s, 30fps | gradient_waves | ~37s |
| Full HD, 5s, 90fps | geometric | ~30s |
| 4K UHD, 3s, 30fps | gradient_waves | ~71s |

If a render takes >2× these times, suspect a worker thread bug or ffmpeg piping issue.

## Seamless loop validation (the headline microstock requirement)

Microstock review will reject any clip whose first and last frames are visibly different. To verify programmatically, the renderer guarantees `render(t=0) == render(t=duration)`. The CLI smoke test in `tests/test_smoke.py` checks this at the pixel level.
