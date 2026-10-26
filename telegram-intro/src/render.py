#!/usr/bin/env python3
"""Digital Journal — intro loop renderer.

Renders the 7-second "living journal" animation frame by frame into PNGs
(1080x1080, 25 fps). Encoding to MP4/GIF is done by export.sh with ffmpeg.

Concept: a blue page sweeps across an empty white sheet. Wherever the page
has passed, the approved DJ monogram is revealed; then the page folds down
into the blue fold of the logo, the exact PNG takes over, the title
appears, and finally the page sweeps back and hides everything, landing on
the first frame for a seamless loop.

Only Pillow and numpy are required. All assets are local (logo PNG + Inter).
"""
import argparse
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "digital_journal_logo.png")
FONT = os.path.join(HERE, "Inter-Medium.otf")

SIZE = 1080
FPS = 25
DURATION = 7.0
N_FRAMES = int(round(FPS * DURATION))  # 175

BLUE = np.array([34, 99, 240], dtype=np.float32)   # sampled from the logo PNG
INK = (20, 20, 20)                                  # sampled from the logo PNG
TITLE = "Digital Journal"

# Placement of the logo artwork (logo-PNG pixel space -> frame space).
LOGO_BBOX = (180, 284, 1073, 1032)  # tight bbox of the monogram in the PNG
SCALE = 0.655
TITLE_SIZE = 58
TITLE_GAP = 76  # monogram bottom -> title cap top

# --- Timeline (seconds) ------------------------------------------------------
T_OPEN = (1.0, 4.2)    # page sweeps, reveals DJ, folds into the logo
T_TITLE_IN = (4.2, 5.0)
T_TITLE_OUT = (5.85, 6.25)
T_CLOSE = (6.0, 7.0)   # page sweeps back and hides everything


# --- Easing / interpolation helpers -----------------------------------------
def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_in_out(x):
    """Cubic-ish ease with soft start/stop (no overshoot)."""
    x = clamp01(x)
    return x * x * x * (x * (6 * x - 15) + 10)  # smootherstep


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def smoothstep(a, b, x):
    t = clamp01((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def pchip(xs, ys, x):
    """Monotone cubic (Fritsch–Carlson) interpolation, scalar."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if d[k - 1] * d[k] <= 0:
            m[k] = 0.0
        else:
            w1 = 2 * h[k] + h[k - 1]
            w2 = h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0] = 0.0   # flat ends: page starts/stops softly
    m[-1] = 0.0
    k = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2))
    t = (x - xs[k]) / h[k]
    h00 = 2 * t**3 - 3 * t**2 + 1
    h10 = t**3 - 2 * t**2 + t
    h01 = -2 * t**3 + 3 * t**2
    h11 = t**3 - t**2
    return h00 * ys[k] + h10 * h[k] * m[k] + h01 * ys[k + 1] + h11 * h[k] * m[k + 1]


# --- Page geometry (logo-PNG pixel space) -----------------------------------
# p = 0: thin page edge at the left of the D (first/last frame)
# p = 1: exactly the blue fold of the approved logo
KEY_P = [0.0, 0.30, 0.62, 1.0]
KEYS = {
    "f":   [148, 330, 600, 751],     # crease edge x (trailing)
    "g":   [170, 830, 1102, 835],    # free edge x (leading)
    "tl":  [268, 262, 262, 371],     # top y at crease
    "tr":  [268, 228, 214, 453],     # top y at free edge (closer -> taller)
    "bl":  [1046, 1052, 1052, 577],  # bottom y at crease
    "br":  [1046, 1086, 1098, 664],  # bottom y at free edge
    "gb":  [0, 46, 34, 0],           # free-edge bulge (x)
    "fb":  [0, -18, -14, 0],         # crease bulge (x)
    "tb":  [0, -10, -8, 0],          # top-edge curl (y)
    "bbx": [0, 0, 0, 24.5],          # bottom-edge control offset x
    "bby": [0, 12, 10, -20.5],       # bottom-edge control offset y
}


def page_params(p, wobble=0.0):
    v = {k: pchip(KEY_P, ys, p) for k, ys in KEYS.items()}
    # idle "breathing" of the page edge before it opens
    v["g"] += 20 * wobble
    v["gb"] += 9 * wobble
    v["tr"] -= 4 * wobble
    v["br"] += 4 * wobble
    return v


def quad_bezier(a, c, b, n=24):
    t = np.linspace(0, 1, n)[:, None]
    a, c, b = map(np.asarray, (a, c, b))
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t**2 * b


def page_polygon(v):
    TL = (v["f"], v["tl"]); TR = (v["g"], v["tr"])
    BR = (v["g"], v["br"]); BL = (v["f"], v["bl"])
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    top = quad_bezier(TL, (mid(TL, TR)[0], mid(TL, TR)[1] + v["tb"]), TR)
    right = quad_bezier(TR, (mid(TR, BR)[0] + v["gb"], mid(TR, BR)[1]), BR)
    m = mid(BR, BL)
    # bottom edge control is defined relative to the BL->BR direction
    bottom = quad_bezier(BR, (m[0] + v["bbx"], m[1] + v["bby"]), BL)
    left = quad_bezier(BL, (mid(BL, TL)[0] + v["fb"], mid(BL, TL)[1]), TL)
    return np.vstack([top, right[1:], bottom[1:], left[1:-1]])


# --- Frame-space transform ---------------------------------------------------
def layout():
    x0, y0, x1, y1 = LOGO_BBOX
    lw, lh = (x1 - x0) * SCALE, (y1 - y0) * SCALE
    font = ImageFont.truetype(FONT, TITLE_SIZE)
    cap = font.getbbox("D")[3] - font.getbbox("D")[1]
    total = lh + TITLE_GAP + cap
    top = (SIZE - total) / 2 - 6  # tiny optical lift
    ox = SIZE / 2 - (x0 + x1) / 2 * SCALE
    oy = top - y0 * SCALE
    return ox, oy, top + lh + TITLE_GAP, font


OX, OY, TITLE_TOP, FONT_OBJ = layout()


def to_frame(pts):
    pts = np.asarray(pts, float)
    return np.column_stack([pts[:, 0] * SCALE + OX, pts[:, 1] * SCALE + OY])


# --- Static layers ------------------------------------------------------------
def build_layers():
    src = Image.open(LOGO).convert("RGB")
    a = np.asarray(src).astype(np.float32)
    # clean JPEG-ish noise in the white field so the background is pure #FFF
    lum = a.min(axis=2, keepdims=True)
    a = np.where(lum > 246, 255.0, a)
    W = src.width
    # place onto frame canvas with high-quality resampling
    big = Image.fromarray(a.astype(np.uint8))
    nw = round(W * SCALE)
    big = big.resize((nw, nw), Image.LANCZOS)
    canvas = Image.new("RGB", (SIZE, SIZE), "white")
    canvas.paste(big, (round(OX), round(OY)))
    full = np.asarray(canvas).astype(np.float32)

    # logo without the blue fold (the moving page plays that role)
    r, g, b = full[..., 0], full[..., 1], full[..., 2]
    blueness = np.clip((b - np.maximum(r, g * 0.9) - 20) / 60, 0, 1)
    noblue = full * (1 - blueness[..., None]) + 255 * blueness[..., None]

    # title mask rendered at 4x for smooth sub-pixel motion
    S = 4
    w = int(FONT_OBJ.getlength(TITLE) * S) + 40
    font4 = ImageFont.truetype(FONT, TITLE_SIZE * S)
    bb = font4.getbbox(TITLE)
    timg = Image.new("L", (bb[2] - bb[0] + 40, bb[3] + 40), 0)
    ImageDraw.Draw(timg).text((20 - bb[0], 20), TITLE, font=font4, fill=255)
    cap4 = font4.getbbox("D")[1]
    return full, noblue, timg, (20 + cap4, S)


def title_alpha(timg, meta, dy, opacity):
    cap_off, S = meta
    out = Image.new("L", (SIZE, SIZE), 0)
    if opacity <= 0:
        return np.zeros((SIZE, SIZE), np.float32)
    tw, th = timg.size
    x = SIZE / 2 - tw / S / 2
    y = TITLE_TOP - cap_off / S + dy
    small = timg.resize((round(tw / S), round(th / S)), Image.LANCZOS,
                        reducing_gap=None)
    # sub-pixel placement via affine shift
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    small = small.transform(small.size, Image.AFFINE, (1, 0, -fx, 0, 1, -fy),
                            resample=Image.BILINEAR)
    out.paste(small, (ix, iy))
    return np.asarray(out).astype(np.float32) / 255 * opacity


def raster(poly_frame, ss=3):
    img = Image.new("L", (SIZE * ss, SIZE * ss), 0)
    ImageDraw.Draw(img).polygon([tuple(p) for p in poly_frame * ss], fill=255)
    img = img.resize((SIZE, SIZE), Image.BOX)
    return np.asarray(img).astype(np.float32) / 255


# --- Timeline state ------------------------------------------------------------
def state(t):
    """Return (phase, p, wobble)."""
    if t < T_OPEN[0]:
        w = math.sin(math.pi * t / T_OPEN[0]) ** 2
        return "open", 0.0, w
    if t < T_CLOSE[0]:
        p = ease_in_out((t - T_OPEN[0]) / (T_OPEN[1] - T_OPEN[0]))
        return "open", p, 0.0
    p = 1 - ease_in_out((t - T_CLOSE[0]) / (T_CLOSE[1] - T_CLOSE[0]))
    return "close", p, 0.0


def render(out_dir, only=None):
    os.makedirs(out_dir, exist_ok=True)
    full, noblue, timg, meta = build_layers()
    xx = np.arange(SIZE, dtype=np.float32)[None, :]
    covered_ever = np.zeros((SIZE, SIZE), np.float32)  # opening: union of page
    hidden_ever = np.zeros((SIZE, SIZE), np.float32)   # closing: union of page
    white = np.full((SIZE, SIZE, 3), 255, np.float32)
    # The opening reveal is cumulative, so simulate every frame in order even
    # when only a few are written.
    for i in range(N_FRAMES):
        t = i / FPS
        phase, p, wob = state(t)
        v = page_params(p, wob)
        poly = to_frame(page_polygon(v))
        cov = raster(poly)

        if phase == "open":
            # the idle breathing before the turn does not reveal anything
            if t >= T_OPEN[0]:
                covered_ever = np.maximum(covered_ever, cov)
            reveal = np.minimum(covered_ever, 1 - cov)
        else:
            hidden_ever = np.maximum(hidden_ever, cov)
            reveal = 1 - hidden_ever
            reveal = np.minimum(reveal, 1 - cov)

        frame = white + (noblue - white) * reveal[..., None]

        # soft contact shadow cast by the lifted page (fades as it settles)
        lift = math.sin(math.pi * p) ** 1.2 if p > 0 else 0.0
        if lift > 0.01:
            sh = Image.fromarray((cov * 255).astype(np.uint8))
            sh = sh.transform(sh.size, Image.AFFINE, (1, 0, -7 * lift, 0, 1, -9 * lift))
            sh = sh.filter(ImageFilter.GaussianBlur(14 * lift + 2))
            sh = np.asarray(sh).astype(np.float32) / 255 * (1 - cov)
            frame *= (1 - 0.13 * lift * sh)[..., None]

        # page colour: slightly deeper toward the crease while it is lifted
        fx, gx = v["f"] * SCALE + OX, v["g"] * SCALE + OX
        u = np.clip((xx - fx) / max(gx - fx, 1), 0, 1)
        shade = 1 - 0.22 * lift * (1 - u) ** 1.5
        page_rgb = BLUE[None, None, :] * shade[..., None]
        page_rgb = np.broadcast_to(page_rgb, (SIZE, SIZE, 3))
        frame = frame + (page_rgb - frame) * cov[..., None]

        # hand-over to the exact approved PNG as the page lands on the fold
        k = smoothstep(0.975, 1.0, p)
        if k > 0:
            frame = frame + (full - frame) * k

        # title
        if T_TITLE_IN[0] <= t < T_TITLE_OUT[0]:
            e = ease_out((t - T_TITLE_IN[0]) / (T_TITLE_IN[1] - T_TITLE_IN[0]))
            ta = title_alpha(timg, meta, 10 * (1 - e), e)
        elif T_TITLE_OUT[0] <= t < T_TITLE_OUT[1]:
            e = ease_in_out((t - T_TITLE_OUT[0]) / (T_TITLE_OUT[1] - T_TITLE_OUT[0]))
            ta = title_alpha(timg, meta, -4 * e, 1 - e)
        else:
            ta = None
        if ta is not None:
            ink = np.array(INK, np.float32)[None, None, :]
            frame = frame + (ink - frame) * ta[..., None]

        if only is None or i in only:
            Image.fromarray(np.clip(frame + 0.5, 0, 255).astype(np.uint8)).save(
                os.path.join(out_dir, f"frame_{i:04d}.png"))
    print(f"rendered {N_FRAMES} frames @ {FPS} fps -> {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "build", "frames"))
    ap.add_argument("--only", default=None,
                    help="comma-separated frame indices to write (debug)")
    a = ap.parse_args()
    only = set(int(x) for x in a.only.split(",")) if a.only else None
    render(a.out, only)
