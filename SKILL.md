---
name: digital-wipe-transition
description: Build whip-pan / slow-shutter "wipe" transitions between two video clips digitally with ffmpeg, no extra footage or phone-sweep trick needed. Use when the user wants a smooth blur-and-slide transition for Reels, TikTok or Shorts, mentions wipe transitions, whip pans, slow shutter, motion-blur or smear transitions, or wants to hide a cut between two clips.
---

# Digital wipe transition

A wipe (whip) transition hides the cut inside a burst of directional motion blur. Clip A smears and slides out, clip B slides in and settles. This skill reproduces that look digitally from the two clips themselves.

## How the in-camera version works (what we imitate)

1. Play clip A on a screen, film it with a phone/camera in slow-shutter mode.
2. During the last moment, sweep the camera sideways: the image becomes a streaked, colour-smeared wipe.
3. In the edit, cut from clip A into that streak, then out of a mirrored streak into clip B.

The streak frames carry the colours of the outgoing clip, so the cut is invisible. The digital version fakes the streak with a directional blur that ramps up on A's tail and ramps down on B's head, with the same sideways slide on both sides.

## Use it

Requires `ffmpeg` and Python 3. No pip packages.

```bash
python3 scripts/wipe.py clipA.mp4 clipB.mp4 out.mp4 \
  --duration 0.5 --direction left
```

The transition overlaps existing frames, so total length is `len(A) + len(B)`. Clip B is scaled/cropped to clip A's size and frame rate. If both clips have audio, a generated whoosh is mixed at the join (`--sfx file.wav` to use your own, `--no-sfx` to skip).

| Flag | Default | Effect |
|------|---------|--------|
| `--duration` | 0.5 | Total seconds (half on each clip). 0.3 is snappy, 0.8 is dreamy |
| `--direction` | left | `left`, `right`, `up`, `down`. Match the camera movement in your footage |
| `--blur` | 1.0 | Smear strength multiplier |
| `--sweep` | 0.5 | How far the image slides (fraction of frame) |
| `--curve` | 2.2 | Ease power. Higher = later, harder snap |
| `--bloom` | 1.0 | Exposure and saturation lift at the peak. 0 turns it off |
| `--fringe` | 0.6 | RGB split at the peak. 0 turns it off |
| `--print-only` | | Print the ffmpeg command instead of running it |

## Workflow for an editor job

1. Pick the cut point. Best when A ends with movement in the same direction as `--direction`, or on a hand, door, pan, or a dark/bright area.
2. Keep both clips at least `duration` long.
3. Run the script, then watch the join frame by frame. If the smear looks flat, raise `--blur` or `--curve`. If the slide feels too big, lower `--sweep`.
4. For a chain of clips, apply it pairwise and concatenate the outputs, or re-run with the previous output as clip A.
5. Always add a whoosh. A wipe without sound feels half done.

## Known limits

- The slide uses wrap-around, so a thin seam can show at the frame edge on mid-transition frames. Lower `--sweep` if it bothers you.
- Variable frame rate sources should be converted to constant frame rate first.
- This is a blur transition, not a luma/mask wipe. For a hard-edged reveal use ffmpeg `xfade` (`wipeleft`, `slideleft`).

Inspired by the in-camera slow-shutter wipe trick shown by Andrik Langfield on Instagram. No footage or assets from that video are used.
