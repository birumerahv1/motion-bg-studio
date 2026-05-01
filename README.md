# Motion Background Studio

Generate seamless looping motion backgrounds (4K MP4) for microstock — Pond5, Shutterstock, Adobe Stock, Pond5, MotionElements, Storyblocks, etc.

Standalone Windows desktop app with a live preview, six built-in styles, curated color palettes, and a render queue for batch production.

## Styles

- **Particles / Bokeh** — drifting soft glowing dots
- **Gradient Waves** — smooth abstract color flow
- **Geometric Shapes** — drifting & rotating polygons
- **Light Leaks** — large soft additive blobs (filmic look)
- **Plexus Network** — connected-dots network
- **Liquid Flow** — warped FBM noise sampled along a closed time-loop path

All styles loop seamlessly: every animation parameter completes an integer number of cycles in the loop duration, and noise is sampled along a closed path through noise-space.

## Quick start (developers)

```bash
uv sync --all-extras

# render one 1080p clip via CLI
uv run motion-bg render --style particles --palette midnight_blue \
  --width 1920 --height 1080 --duration 6 --fps 30 --seed 42 -o sample.mp4

# render 10 4K variations of liquid into ./renders
uv run motion-bg batch --style liquid --count 10

# launch the desktop app
uv run motion-bg-studio
```

Requires `ffmpeg` on PATH (the bundled Windows installer ships a copy alongside the `.exe`).

## Windows installer

CI builds a standalone Windows `.exe` on every push. Grab the latest from the
**Releases** tab or the **Actions → build-windows** workflow artifacts. No
Python install needed on the user's machine.

## License

MIT
