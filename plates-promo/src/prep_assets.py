#!/usr/bin/env python3
"""Prepare clean UI material for the Plates promo from the raw screen recording.

    python3 src/prep_assets.py --app <screen-recording.mov> --logo <logo.png>

What it does (privacy first):
  * extracts frames, measures the scroll between them and stitches the three
    scrolling screens (Тренировка, Прогресс, Программа) into long pages,
    using only the clean middle band of each frame;
  * removes the status bar / Dynamic Island, the body-weight figures in the
    header (62,5 → 70, ring 64,2) and the whole «Вес тела» card;
  * never touches the Settings screen (name, account, sync/logout);
  * cuts the bottom overlays (save bar, tab bar), the exercise dropdown,
    the program cards for the montage, an "empty chart" plate for the
    draw-on animation, and a white-on-transparent version of the logo.
"""
import argparse
import json
import os
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "assets")
FR = os.path.join(ROOT, "build", "src30")
W = 512

# Frame ranges in the recording (1-based frame numbers, 30 fps)
TRAINING = (1, 533)    # 0:00–0:17  Тренировка, scrolled top → bottom
PROGRESS = (554, 650)  # 0:18–0:21  Прогресс
DROPDOWN = 700         # 0:23       exercise picker open
PROGRAM = (740, 1090)  # 0:24–0:36  Программа (Settings start after this — unused)


def L(n):
    return np.asarray(Image.open(os.path.join(FR, f"f_{n:04d}.png")).convert("RGB"))


def extract(app):
    if os.path.isdir(FR) and len(os.listdir(FR)) > 1200:
        return
    os.makedirs(FR, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", app, "-vsync", "0",
                    os.path.join(FR, "f_%04d.png")], check=True)


def measure_scroll(a, b, y0=70, y1=900):
    """Vertical content shift between consecutive frames (positive = scrolled down)."""
    cache = os.path.join(ROOT, "build", f"scroll_{a}_{b}.json")
    if os.path.exists(cache):
        return {int(k): v for k, v in json.load(open(cache)).items()}
    sh = {}
    prev = L(a).astype(np.int16)
    for n in range(a + 1, b + 1):
        cur = L(n).astype(np.int16)
        best = (1e9, 0)
        for s in range(-60, 121):
            if s >= 0:
                d = np.abs(prev[y0 + s:y1, ::2] - cur[y0:y1 - s, ::2]).mean()
            else:
                d = np.abs(prev[y0:y1 + s, ::2] - cur[y0 - s:y1, ::2]).mean()
            if d < best[0]:
                best = (d, s)
        sh[n] = best[1]
        prev = cur
    json.dump(sh, open(cache, "w"))
    return sh


def stitch(a, b, M0=190, M1=860, TOP=60, tail=None):
    sh = measure_scroll(a, b)
    off = {a: 0}
    for n in range(a + 1, b + 1):
        off[n] = off[n - 1] + sh[n]
    hi = max(off.values())
    extra = (tail - M1) if tail else 0
    page = np.zeros((M1 + hi + extra, W, 3), np.uint8)
    page[TOP:M1] = L(a)[TOP:M1]
    for n in sorted(range(a, b + 1), key=lambda n: -abs(sh.get(n, 0))):  # sharpest last
        page[off[n] + M0:off[n] + M1] = L(n)[M0:M1]
    if tail:  # bottom of the page from the last, resting frame
        page[off[b] + M1:off[b] + tail] = L(b)[M1:tail]
    return page


def clean_edges(img, top=92):
    """Remove status bar / island (fill with the row just below) and the scrollbar."""
    img = img.copy()
    img[:top] = img[top]
    img[:, 501:] = img[:, 500:501]
    return img


def fill_rect_from_column(img, x0, y0, x1, y1, src_x):
    img[y0:y1, x0:x1] = img[y0:y1, src_x:src_x + 1]


def rgba(arr, alpha):
    return Image.fromarray(np.dstack([arr, (np.clip(alpha, 0, 1) * 255).astype(np.uint8)]))


def ramp(h, w, start, length):
    y = np.arange(h, dtype=np.float32)[:, None]
    return np.broadcast_to(np.clip((y - start) / length, 0, 1), (h, w))


def round_mask(h, w, r, feather=1.5):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = np.maximum(np.maximum(r - xx, xx - (w - 1 - r)), 0)
    dy = np.maximum(np.maximum(r - yy, yy - (h - 1 - r)), 0)
    d = np.sqrt(dx ** 2 + dy ** 2) - r
    return np.clip(0.5 - d / feather, 0, 1)


def card_slices(page, y_from):
    """Row ranges of the UI cards (split in the dark gaps between them)."""
    mid = page[:, 40:470].astype(np.int16)
    quiet = (mid.std(axis=(1, 2)) < 3.0) & (mid.mean(axis=(1, 2)) < 22)
    cuts, y = [], y_from
    while y < len(page):
        if quiet[y]:
            y2 = y
            while y2 < len(page) and quiet[y2]:
                y2 += 1
            if y2 - y >= 6:
                cuts.append((y + y2) // 2)
            y = y2
        y += 1
    return cuts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--logo", required=True)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    extract(a.app)
    meta = {}

    # ---- Тренировка: long page, header without body-weight data
    tr = stitch(*TRAINING)
    tr = clean_edges(tr)
    fill_rect_from_column(tr, 0, 177, 300, 228, 300)     # «62,5 → 70»
    fill_rect_from_column(tr, 340, 88, 501, 236, 330)    # ring «64,2 из 70 кг»
    Image.fromarray(tr).save(os.path.join(OUT, "training_page.png"))
    meta["training"] = {"h": len(tr), "cuts": card_slices(tr, 236)}
    f1 = L(1)
    over = f1[870:1108]
    Image.fromarray(np.dstack([over, (ramp(len(over), W, 0, 40) * 255).astype(np.uint8)])) \
        .save(os.path.join(OUT, "training_overlay.png"))
    meta["training_overlay_y"] = 870

    # ---- Прогресс: title + «История упражнения» only (no body-weight card)
    pr = stitch(*PROGRESS, tail=990)
    pr = clean_edges(pr, top=68)
    pr = np.concatenate([pr[:172], pr[845:]], axis=0)
    shift = 845 - 172
    # chart plate for the draw-on: same pixels with the orange line/fill removed
    # every plot row = its own median colour (keeps the grid lines, drops line/fill/dots)
    cx0, cy0, cx1, cy1 = 72, 985 - shift, 474, 1112 - shift
    plot = pr[cy0:cy1, cx0:cx1].astype(np.int16)
    warm = (plot[..., 0] - plot[..., 2]) > 6
    empty = pr.copy()
    for r in range(cy1 - cy0):
        row = plot[r][~warm[r]]
        if len(row) < 20:
            row = plot[r]
        empty[cy0 + r, cx0:cx1] = np.median(row, axis=0)
    Image.fromarray(pr).save(os.path.join(OUT, "progress_page.png"))
    Image.fromarray(empty).save(os.path.join(OUT, "progress_page_empty_chart.png"))
    meta["progress"] = {"h": len(pr), "chart": [cx0, cy0, cx1, cy1], "card_top": 175}
    f640 = L(640)
    tab = f640[950:1108]
    Image.fromarray(np.dstack([tab, (ramp(len(tab), W, 0, 36) * 255).astype(np.uint8)])) \
        .save(os.path.join(OUT, "progress_overlay.png"))
    meta["progress_overlay_y"] = 950

    # ---- dropdown (exercise picker), positioned relative to the history card
    f700 = L(DROPDOWN)
    dx0, dy0, dx1, dy1 = 100, 290, 426, 966
    dd = f700[dy0:dy1, dx0:dx1]
    rgba(dd, round_mask(dy1 - dy0, dx1 - dx0, 26)).save(os.path.join(OUT, "dropdown.png"))
    # select field highlight (orange outline) from the same frame
    sel = f700[282:346, 40:486]
    rgba(sel, round_mask(346 - 282, 486 - 40, 16)).save(os.path.join(OUT, "select_active.png"))
    card_top_700 = 220
    meta["dropdown"] = {"x": dx0, "y": dy0 - card_top_700 + 175,
                        "select": [40, 282 - card_top_700 + 175]}

    # ---- Программа: cards for the montage
    pg = stitch(*PROGRAM)
    pg = clean_edges(pg, top=68)
    Image.fromarray(pg).save(os.path.join(OUT, "program_page.png"))
    for name, (y0, y1) in {"card_schedule": (176, 709), "card_table": (727, 1372)}.items():
        c = pg[y0:y1, 22:502]
        alpha = round_mask(y1 - y0, 480, 30)
        if name == "card_table":
            alpha = alpha * (1 - ramp(y1 - y0, 480, (y1 - y0) - 140, 140))
        rgba(c, alpha).save(os.path.join(OUT, name + ".png"))

    # ---- logo: black marks on a light disc -> white marks on transparent
    lg = np.asarray(Image.open(a.logo).convert("L")).astype(np.float32)
    alpha = np.clip((170 - lg) / 120, 0, 1)
    ys, xs = np.nonzero(alpha > 0.5)
    pad = 8
    alpha = alpha[ys.min() - pad:ys.max() + pad, xs.min() - pad:xs.max() + pad]
    white = np.full(alpha.shape + (3,), 255, np.uint8)
    rgba(white, alpha).save(os.path.join(OUT, "logo_white.png"))

    # ---- film grain tile
    rng = np.random.default_rng(7)
    g = rng.normal(128, 40, (512, 512)).clip(0, 255).astype(np.uint8)
    Image.fromarray(g).filter(ImageFilter.GaussianBlur(0.6)).save(os.path.join(OUT, "grain.png"))

    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(json.dumps(meta)[:600])


if __name__ == "__main__":
    main()
