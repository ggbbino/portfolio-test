#!/usr/bin/env python3
"""Full export + checks for the Digital Journal emoji set.

    python3 src/export.py

1. build_tgs.py  -> tgs/*.tgs (+ plain Lottie JSON in build/lottie)
2. render_frames.js renders that same Lottie in Chromium (lottie-web)
3. webm/*.webm   100x100, VP9 + alpha, 30 fps, 3.0 s, no audio
4. preview/digital_journal_emoji_preview.gif  dark 2x2 sheet with labels
5. checks (printed and saved to build/report.txt), ZIP of everything
"""
import argparse
import gzip
import json
import os
import shutil
import subprocess
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "build")
NAMES = ["navigation", "projects", "business", "notes"]
LABELS = {"navigation": "Навигация", "projects": "Проекты",
          "business": "Своё дело", "notes": "Личные заметки"}
FONT = os.path.join(SRC, "Inter-Medium.otf")
BG = (17, 19, 24)
FORBIDDEN_KEYS = {"ef", "masksProperties", "tt", "td", "x"}  # effects, masks, mattes, expressions
FORBIDDEN_SHAPES = {"rp", "mm", "sr", "gs"}  # repeater, merge paths, star, gradient stroke
ALLOWED_LAYERS = {3, 4}  # null, shape


def run(*cmd):
    subprocess.run(cmd, check=True)


def render(lib, name, size, step, out):
    shutil.rmtree(out, ignore_errors=True)
    run("node", os.path.join(SRC, "render_frames.js"), lib,
        os.path.join(BUILD, "lottie", name + ".json"), out, str(size), str(step))
    return sorted(os.path.join(out, f) for f in os.listdir(out))


def to_rgba_small(path, size):
    im = Image.open(path).convert("RGBA")
    # premultiplied resize avoids dark fringes on transparent edges
    return im.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def scan(node, problems, where="root"):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in FORBIDDEN_KEYS and not (k == "x" and isinstance(v, list)):
                problems.append(f"{where}: forbidden key '{k}'")
            if k == "ty" and v in FORBIDDEN_SHAPES:
                problems.append(f"{where}: forbidden shape '{v}'")
            scan(v, problems, where)
    elif isinstance(node, list):
        for v in node:
            scan(v, problems, where)


def check_tgs(path):
    raw = open(path, "rb").read()
    d = json.loads(gzip.decompress(raw))
    probs = []
    for key, want in (("tgs", 1), ("fr", 60), ("ip", 0), ("w", 512), ("h", 512), ("ddd", 0)):
        if d.get(key) != want:
            probs.append(f"{key}={d.get(key)} (need {want})")
    if not (0 < d["op"] <= 180):
        probs.append(f"op={d['op']} (need <= 180)")
    if d.get("assets"):
        probs.append("has assets (images/precomps)")
    for l in d["layers"]:
        if l["ty"] not in ALLOWED_LAYERS:
            probs.append(f"layer type {l['ty']}")
        if l.get("ddd"):
            probs.append("3D layer")
    scan(d["layers"], probs)
    if len(raw) > 64 * 1024:
        probs.append("size > 64 KB")
    return d, len(raw), probs


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames:"
                          "stream_tags=alpha_mode:format=duration,size",
                          "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lottie-web", default=os.path.join(SRC, "vendor", "lottie.min.js"),
                    help="lottie-web 5.12.2 player (bundled in src/vendor)")
    a = ap.parse_args()
    lib = a.lottie_web

    run("python3", os.path.join(SRC, "build_tgs.py"))
    for d in ("webm", "preview"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)

    report = []
    say = lambda s="": (print(s), report.append(s))
    frames30 = {}
    for n in NAMES:
        # 60 fps master render (for the loop/motion/crop checks)
        f60 = render(lib, n, 256, 1, os.path.join(BUILD, "f60", n))
        # 30 fps render for WEBM / GIF
        f30 = render(lib, n, 400, 2, os.path.join(BUILD, "f30", n))
        small = os.path.join(BUILD, "webm_frames", n)
        shutil.rmtree(small, ignore_errors=True)
        os.makedirs(small)
        frames30[n] = []
        for i, p in enumerate(f30):
            im = to_rgba_small(p, 100)
            im.save(os.path.join(small, f"f_{i:04d}.png"))
            frames30[n].append(p)
        run("ffmpeg", "-loglevel", "error", "-y", "-framerate", "30",
            "-i", os.path.join(small, "f_%04d.png"),
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
            "-deadline", "good", "-row-mt", "1", "-an", "-auto-alt-ref", "0",
            os.path.join(ROOT, "webm", n + ".webm"))

        # ---- checks
        say(f"== {LABELS[n]} ({n})")
        d, size, probs = check_tgs(os.path.join(ROOT, "tgs", n + ".tgs"))
        say(f"TGS: {d['w']}x{d['h']}, {d['fr']} fps, {d['op'] - d['ip']} frames = "
            f"{(d['op'] - d['ip']) / d['fr']:.2f} s, {size / 1024:.1f} KB, "
            f"{'OK' if not probs else 'PROBLEMS: ' + '; '.join(probs)}")
        w = probe(os.path.join(ROOT, "webm", n + ".webm"))
        v = [s for s in w["streams"] if s["codec_type"] == "video"][0]
        audio = [s for s in w["streams"] if s["codec_type"] == "audio"]
        wsize = int(w["format"]["size"])
        say(f"WEBM: {v['codec_name']}, {v['width']}x{v['height']}, {v['r_frame_rate']} fps, "
            f"{v['nb_read_frames']} frames, {float(w['format']['duration']):.2f} s, "
            f"{wsize / 1024:.1f} KB, alpha_mode={v.get('tags', {}).get('alpha_mode')}, "
            f"audio streams={len(audio)}")
        # decode the WEBM back with alpha to prove transparency survives
        dec = subprocess.run(["ffmpeg", "-loglevel", "error", "-c:v", "libvpx-vp9", "-i",
                              os.path.join(ROOT, "webm", n + ".webm"), "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                             capture_output=True, check=True).stdout
        alpha = np.frombuffer(dec, np.uint8).reshape(100, 100, 4)[..., 3]
        say(f"WEBM decoded alpha: corner={alpha[0, 0]}, transparent px={np.mean(alpha < 8):.0%}")

        arr = [np.asarray(Image.open(p).convert("RGBA")).astype(np.int16) for p in f60]
        steps = [np.abs(arr[i + 1] - arr[i]).mean() for i in range(len(arr) - 1)]
        seam = np.abs(arr[0] - arr[-1]).mean()
        moving = sum(s > 0.01 for s in steps)
        border = max(int(np.max(np.concatenate([x[0, :, 3], x[-1, :, 3], x[:, 0, 3],
                                                x[:, -1, 3]]))) for x in arr)
        say(f"Motion: {moving}/{len(steps)} frame steps move, max step {max(steps):.2f}, "
            f"loop seam (last->first) {seam:.3f}")
        say(f"Crop: max alpha on canvas edge across all frames = {border} (0 = nothing cut)")
        say()

    # ---- 2x2 preview GIF on a dark background (30 fps)
    font = ImageFont.truetype(FONT, 26)
    N = len(frames30[NAMES[0]])
    pv = os.path.join(BUILD, "preview_frames")
    shutil.rmtree(pv, ignore_errors=True)
    os.makedirs(pv)
    cells = [(0, 0), (1, 0), (0, 1), (1, 1)]
    for i in range(N):
        canvas = Image.new("RGBA", (640, 640), BG + (255,))
        dr = ImageDraw.Draw(canvas)
        for n, (cx, cy) in zip(NAMES, cells):
            ox, oy = cx * 320, cy * 320
            icon = to_rgba_small(frames30[n][i], 176)
            canvas.alpha_composite(icon, (ox + 72, oy + 40))
            tw = dr.textlength(LABELS[n], font=font)
            dr.text((ox + 160 - tw / 2, oy + 238), LABELS[n], font=font, fill=(255, 255, 255))
        canvas.convert("RGB").save(os.path.join(pv, f"f_{i:04d}.png"))
    gif = os.path.join(ROOT, "preview", "digital_journal_emoji_preview.gif")
    run("ffmpeg", "-loglevel", "error", "-y", "-framerate", "30", "-i",
        os.path.join(pv, "f_%04d.png"), "-vf",
        "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", gif)
    say(f"Preview GIF: {os.path.getsize(gif) / 1024:.0f} KB")

    # ---- 24 px readability sheet (several moments of each loop)
    idx = [0, 15, 24, 33, 42, 51, 60, 75]
    sheet = Image.new("RGBA", (len(idx) * 28 + 4, len(NAMES) * 28 + 4), BG + (255,))
    for r, n in enumerate(NAMES):
        for c, i in enumerate(idx):
            sheet.alpha_composite(to_rgba_small(frames30[n][i], 24), (4 + c * 28, 4 + r * 28))
    sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST).save(
        os.path.join(ROOT, "preview", "check_24px_x4.png"))

    with open(os.path.join(BUILD, "report.txt"), "w") as f:
        f.write("\n".join(report) + "\n")
    shutil.copy(os.path.join(BUILD, "report.txt"), os.path.join(ROOT, "preview", "checks.txt"))

    # ---- ZIP
    zpath = os.path.join(ROOT, "digital_journal_emoji.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for d in ("tgs", "webm", "preview", "src"):
            for base, dirs, files in os.walk(os.path.join(ROOT, d)):
                dirs[:] = [x for x in dirs if x != "__pycache__"]
                for fn in sorted(files):
                    p = os.path.join(base, fn)
                    z.write(p, "digital_journal_emoji/" + os.path.relpath(p, ROOT))
        z.write(os.path.join(ROOT, "README.md"), "digital_journal_emoji/README.md")
    print(f"ZIP: {zpath} ({os.path.getsize(zpath) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
