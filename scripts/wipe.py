#!/usr/bin/env python3
"""Digital whip / slow-shutter wipe transition between two clips.

Pure stdlib + ffmpeg. The end of clip A is smeared and swept off-screen,
the start of clip B is swept in and settles. The cut is hidden at the
moment both sides are maximum smear, like the in-camera "phone sweep" trick.

    python3 wipe.py a.mp4 b.mp4 out.mp4 --duration 0.5 --direction left
"""
import argparse, json, subprocess, sys


def probe(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
        "-show_format", path])
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    num, den = v["r_frame_rate"].split("/")
    return {
        "w": int(v["width"]), "h": int(v["height"]),
        "fps": float(num) / float(den),
        "dur": float(j["format"]["duration"]),
        "audio": any(s["codec_type"] == "audio" for s in j["streams"]),
    }


def ease(t, power):
    return t ** power


def seg(src, f0, f1, e, args, W, H, label, at):
    """One processed frame: trim -> smear -> sweep -> exposure/colour."""
    chain = [f"trim=start_frame={f0}:end_frame={f1}", f"setpts=PTS-STARTPTS+{at:.6f}/TB"]
    sig = max(0.0, args.blur * W * 0.35 * e)
    horiz = args.direction in ("left", "right")
    if sig > 0.4:
        s_h, s_v = (sig, 0.0) if horiz else (0.0, sig * H / W)
        chain.append(f"gblur=sigma={s_h:.2f}:sigmaV={s_v:.2f}:steps=3")
    shift = min(0.999, args.sweep * e)
    if shift > 0:
        # scroll wraps; the smear hides the seam
        pos = shift if args.direction in ("left", "up") else 1 - shift
        key = "hpos" if horiz else "vpos"
        chain.append(f"scroll={key}={pos:.4f}")
    if args.bloom > 0 and e > 0:
        chain.append(f"eq=brightness={0.10 * args.bloom * e:.3f}:"
                     f"saturation={1 + 0.5 * args.bloom * e:.3f}")
    if args.fringe > 0 and e > 0.05:
        px = max(1, round(args.fringe * W * 0.01 * e))
        if horiz:
            chain.append(f"rgbashift=rh={-px}:bh={px}:edge=smear")
        else:
            chain.append(f"rgbashift=rv={-px}:bv={px}:edge=smear")
    return f"[{src}]" + ",".join(chain) + f"[{label}]"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("a"); p.add_argument("b"); p.add_argument("out")
    p.add_argument("--duration", type=float, default=0.5,
                   help="total transition seconds (default 0.5)")
    p.add_argument("--direction", choices=["left", "right", "up", "down"], default="left")
    p.add_argument("--blur", type=float, default=1.0, help="smear strength multiplier")
    p.add_argument("--sweep", type=float, default=0.5, help="how far content slides (0-1 of frame)")
    p.add_argument("--curve", type=float, default=2.2, help="ease power; higher = snappier")
    p.add_argument("--bloom", type=float, default=1.0, help="exposure/saturation lift at peak (0=off)")
    p.add_argument("--fringe", type=float, default=0.6, help="RGB split at peak (0=off)")
    p.add_argument("--sfx", help="whoosh audio file; default is a generated whoosh")
    p.add_argument("--no-sfx", action="store_true")
    p.add_argument("--crf", type=int, default=16)
    p.add_argument("--print-only", action="store_true")
    args = p.parse_args()

    A, B = probe(args.a), probe(args.b)
    W, H, fps = A["w"] - A["w"] % 2, A["h"] - A["h"] % 2, A["fps"]
    n = max(2, round(args.duration * fps / 2))
    fa, fb = round(A["dur"] * fps), round(B["dur"] * fps)
    if fa <= n or fb <= n:
        sys.exit("clips are shorter than half the transition duration")

    norm = (f"fps={fps:.5f},scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,format=yuv420p")
    g = [f"[0:v]{norm},split={n + 1}" + "".join(f"[a{i}]" for i in range(n + 1)),
         f"[1:v]{norm},split={n + 1}" + "".join(f"[b{i}]" for i in range(n + 1))]
    g[0] = g[0].replace("[a%d]" % n, "[abody]").replace("[a0]", "[a0]")
    # A body: everything before the tail
    g.append(f"[abody]trim=end_frame={fa - n},setpts=PTS-STARTPTS[ahead]")
    labels = ["[ahead]"]
    for i in range(n):                       # A tail: ramp up (e: 0 -> 1)
        t = (i + 1) / n
        e = ease(t, args.curve)
        f = fa - n + i
        g.append(seg(f"a{i}", f, f + 1, e, args, W, H, f"ao{i}", f / fps))
        labels.append(f"[ao{i}]")
    for i in range(n):                       # B head: ramp down (e: 1 -> 0)
        t = 1 - i / n
        e = ease(t, args.curve)
        # B enters from the side A left to, so the motion reads as one sweep
        bargs = argparse.Namespace(**vars(args))
        bargs.direction = {"left": "right", "right": "left", "up": "down", "down": "up"}[args.direction]
        g.append(seg(f"b{i}", i, i + 1, e, bargs, W, H, f"bo{i}", (fa + i) / fps))
        labels.append(f"[bo{i}]")
    g.append(f"[b{n}]trim=start_frame={n},setpts=PTS-STARTPTS+{(fa + n) / fps:.6f}/TB[btail]")
    labels.append("[btail]")
    g.append("".join(labels) + f"interleave=nb_inputs={len(labels)}[v]")

    cmd = ["ffmpeg", "-v", "error", "-y", "-i", args.a, "-i", args.b]
    maps = ["-map", "[v]"]
    use_audio = A["audio"] and B["audio"]
    sfx_in = []
    if use_audio:
        g.append("[0:a]aformat=sample_rates=48000:channel_layouts=stereo[aa]")
        g.append("[1:a]aformat=sample_rates=48000:channel_layouts=stereo[ba]")
        g.append("[aa][ba]concat=n=2:v=0:a=1[ab]")
        if args.no_sfx:
            g.append("[ab]anull[aout]")
        else:
            D = args.duration
            delay = max(0, int((A["dur"] - D * 0.55) * 1000))
            if args.sfx:
                cmd += ["-i", args.sfx]
                src = "[2:a]aformat=sample_rates=48000:channel_layouts=stereo"
            else:
                src = (f"anoisesrc=d={D * 1.4:.3f}:c=pink:a=0.6:r=48000,"
                       f"bandpass=f=1800:width_type=q:w=0.6,"
                       f"afade=t=in:d={D * 0.7:.3f},afade=t=out:st={D * 0.7:.3f}:d={D * 0.7:.3f},"
                       f"aformat=channel_layouts=stereo")
            g.append(f"{src},adelay={delay}|{delay},volume=0.8[sfx]")
            g.append("[ab][sfx]amix=inputs=2:normalize=0:duration=first[aout]")
        maps += ["-map", "[aout]"]
    cmd += ["-filter_complex", ";".join(g)] + maps + [
        "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if use_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += [args.out]
    if args.print_only:
        print(" ".join(cmd)); return
    subprocess.check_call(cmd)
    print(f"wrote {args.out}  ({n} frames per side at {fps:.2f} fps)")


if __name__ == "__main__":
    main()
