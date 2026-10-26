#!/usr/bin/env python3
"""Digital Journal — animated custom emoji (Telegram TGS / Lottie).

Builds four Lottie animations by hand (no AE / no plugins) that stay inside
Telegram's TGS limits: 512x512, 60 fps, <= 180 frames, shape layers only —
no images, masks, mattes, expressions, repeaters, merge paths or text.

    python3 build_tgs.py --out ../build/lottie

writes <name>.json (plain Lottie, for rendering/previews) and the TGS files
(gzip-compressed Lottie with "tgs": 1) to ../tgs/.
"""
import argparse
import gzip
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 60
OP = 180  # 3.0 s

# Palette sampled from the approved icons
WHITE = [250 / 255, 251 / 255, 255 / 255, 1]
BLUE = [37 / 255, 99 / 255, 250 / 255, 1]
INK = [9 / 255, 11 / 255, 18 / 255, 1]
OUTLINE = 18  # outline width on the 512 canvas


# --- easing -------------------------------------------------------------------
EASE = ((0.42, 0.0), (0.58, 1.0))       # soft in-out
EASE_OUT = ((0.25, 0.0), (0.2, 1.0))     # quick start, long settle
EASE_IN = ((0.55, 0.0), (0.8, 1.0))
LINEAR = ((0.0, 0.0), (1.0, 1.0))


def anim(keys, dims=None):
    """keys: list of (frame, value, ease_to_next | 'hold' | None)."""
    out = []
    for i, (t, v, e) in enumerate(keys):
        v = v if isinstance(v, list) else [v]
        n = len(v)
        k = {"t": t, "s": v}
        if i < len(keys) - 1:
            if e == "hold":
                k["h"] = 1
            else:
                (ox, oy), (ix, iy) = e or EASE
                k["o"] = {"x": [ox] * n, "y": [oy] * n}
                k["i"] = {"x": [ix] * n, "y": [iy] * n}
        out.append(k)
    return {"a": 1, "k": out}


def static(v):
    return {"a": 0, "k": v}


# --- shape helpers ---------------------------------------------------------------
def rect(cx, cy, w, h, r=0):
    return {"ty": "rc", "d": 1, "p": static([cx, cy]), "s": static([w, h]), "r": static(r)}


def ellipse(cx, cy, d):
    return {"ty": "el", "d": 1, "p": static([cx, cy]), "s": static([d, d])}


def path(points, closed=True, tangents=None):
    n = len(points)
    ins = [[0, 0]] * n
    outs = [[0, 0]] * n
    if tangents:
        ins = [t[0] for t in tangents]
        outs = [t[1] for t in tangents]
    return {"ty": "sh", "d": 1, "ks": static({"c": closed, "v": [list(p) for p in points],
                                               "i": ins, "o": outs})}


def fill(color):
    return {"ty": "fl", "c": static(color), "o": static(100), "r": 1}


def stroke(color, width, cap=2, join=2):
    return {"ty": "st", "c": static(color), "o": static(100), "w": static(width),
            "lc": cap, "lj": join, "ml": 4}


def trim(end, start=None):
    return {"ty": "tm", "s": start if start is not None else static(0), "e": end,
            "o": static(0), "m": 1}


def xform(p=(0, 0), a=(0, 0), s=None, r=None, o=None):
    def val(x, default):
        if x is None:
            return static(default)
        if isinstance(x, dict):
            return x
        return static(list(x) if isinstance(x, tuple) else x)
    return {"ty": "tr", "p": val(p, [0, 0]), "a": val(a, [0, 0]), "s": val(s, [100, 100]),
            "r": val(r, 0), "o": val(o, 100), "sk": static(0), "sa": static(0)}


def group(name, items, tr=None):
    return {"ty": "gr", "nm": name, "it": items + [tr or xform()]}


def solid(name, shape, color, outline=OUTLINE):
    """Filled shape with a dark outline drawn on top."""
    items = [shape]
    if outline:
        items.append(stroke(INK, outline))
    items.append(fill(color))
    return group(name, items)


def document(name, groups):
    layer = {
        "ddd": 0, "ind": 1, "ty": 4, "nm": name, "sr": 1,
        "ks": {"o": static(100), "r": static(0), "p": static([0, 0, 0]),
               "a": static([0, 0, 0]), "s": static([100, 100, 100])},
        "ao": 0, "shapes": groups, "ip": 0, "op": OP, "st": 0, "bm": 0,
    }
    return {"tgs": 1, "v": "5.5.2", "fr": FPS, "ip": 0, "op": OP, "w": 512, "h": 512,
            "nm": name, "ddd": 0, "assets": [], "layers": [layer]}


# --- 1. Навигация: компас -------------------------------------------------------
def compass():
    C = 256
    # needle: looks for the bearing — swings, overshoots, corrects, settles
    rot = anim([
        (0, 0, "hold"), (14, 0, EASE), (46, 44, EASE), (76, -18, EASE),
        (100, 10, EASE), (120, -3, EASE), (138, 0, None),
    ])
    needle = group("needle", [
        solid("cap", ellipse(C, C, 46), WHITE, outline=10),
        solid("north", path([(C, C - 142), (C + 30, C), (C - 30, C)]), BLUE, outline=0),
        solid("south", path([(C - 30, C), (C + 30, C), (C, C + 142)]), WHITE, outline=0),
    ], xform(p=(C, C), a=(C, C), r=rot))
    ticks = group("ticks", [
        rect(C, C - 188, 24, 46, 12), rect(C, C + 188, 24, 46, 12),
        rect(C - 188, C, 46, 24, 12), rect(C + 188, C, 46, 24, 12),
        fill(BLUE),
    ])
    face = group("face", [ellipse(C, C, 322), fill(INK)])
    ring = solid("ring", ellipse(C, C, 438), WHITE)
    return document("Навигация", [needle, ticks, face, ring])


# --- 2. Проекты: папка с документом -----------------------------------------------
def projects():
    rest, up = 300, 172
    doc_pos = anim([
        (0, [256, rest], "hold"), (16, [256, rest], EASE_OUT), (58, [256, up], "hold"),
        (118, [256, up], EASE), (154, [256, rest], None),
    ])
    check_e = anim([
        (0, 0, "hold"), (52, 0, EASE), (80, 100, "hold"), (150, 100, "hold"), (151, 0, None),
    ])
    check_o = anim([
        (0, 100, "hold"), (118, 100, EASE), (136, 0, "hold"), (151, 0, "hold"), (152, 100, None),
    ])
    check = group("check", [
        path([(-52, -66), (-14, -30), (54, -98)], closed=False),
        trim(check_e),
        stroke(BLUE, 28),
    ], xform(o=check_o))
    sheet = group("document", [
        check,
        solid("paper", rect(0, 0, 220, 250, 18), WHITE),
    ], xform(p=doc_pos))
    # the pocket gives a small, firm "catch" when the document drops back in
    pocket_s = anim([
        (0, [100, 100], "hold"), (150, [100, 100], EASE_OUT), (158, [101.5, 97.5], EASE),
        (172, [100, 100], None),
    ])
    pocket = group("pocket", [
        solid("front", path([(68, 252), (444, 252), (414, 442), (98, 442)]), BLUE),
    ], xform(p=(256, 442), a=(256, 442), s=pocket_s))
    back = solid("back", path([(92, 340), (92, 132), (196, 132), (224, 162), (420, 162),
                               (420, 340)]), WHITE)
    return document("Проекты", [pocket, sheet, back])


# --- 3. Своё дело: портфель -------------------------------------------------------
def business():
    pivot = (256, 112)  # the case hangs from its handle
    lift = anim([
        (0, [256, 112], "hold"), (12, [256, 112], EASE), (44, [256, 80], "hold"),
        (110, [256, 80], EASE), (140, [256, 112], None),
    ])
    sway = anim([
        (0, 0, "hold"), (30, 0, EASE), (58, 6, EASE), (84, -4.5, EASE), (106, 2, EASE),
        (128, 0, None),
    ])
    land = anim([
        (0, [100, 100], "hold"), (138, [100, 100], EASE_OUT), (146, [101.2, 98], EASE),
        (160, [100, 100], None),
    ])
    handle_r = anim([  # follows the sway with a little lag
        (0, 0, "hold"), (36, 0, EASE), (66, -8, EASE), (92, 6, EASE), (114, -2.5, EASE),
        (134, 0, None),
    ])
    clasp_p = anim([
        (0, [256, 292], "hold"), (14, [256, 292], EASE), (30, [256, 296], EASE),
        (48, [256, 292], "hold"), (140, [256, 292], EASE), (150, [256, 296], EASE),
        (164, [256, 292], None),
    ])
    handle = group("handle", [
        path([(198, 180), (198, 122), (314, 122), (314, 180)], closed=False),
        stroke(WHITE, 24, cap=2, join=2),
        path([(198, 180), (198, 122), (314, 122), (314, 180)], closed=False),
        stroke(INK, 52, cap=2, join=2),
    ], xform(p=(256, 180), a=(256, 180), r=handle_r))
    clasp = group("clasp", [rect(0, 0, 58, 50, 10), fill(BLUE)], xform(p=clasp_p))
    band = group("band", [rect(256, 292, 364, 20, 0), fill(BLUE)])
    body = group("body", [
        clasp, band,
        solid("case", rect(256, 300, 384, 252, 38), WHITE),
    ], xform(p=(256, 426), a=(256, 426), s=land))
    case = group("briefcase", [body, handle], xform(p=lift, a=pivot, r=sway))
    return document("Своё дело", [case])


# --- 4. Личные заметки: лист и перо ---------------------------------------------
def notes():
    # handwriting stroke: pen and line share the same points and timing
    pts = [(160, 325), (184, 320), (208, 327), (232, 320), (256, 326), (280, 323)]
    frames = [44, 54, 64, 74, 84, 94]
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg)
    cum = [0.0]
    for s in seg:
        cum.append(cum[-1] + s)
    write_ease = [((0.5, 0.0), (1.0, 1.0))] + [LINEAR] * (len(pts) - 2)

    rest = [318, 400]
    pos = [(0, rest, "hold"), (18, rest, EASE)]
    trim_e = [(0, 0, "hold")]
    for i, (f, p) in enumerate(zip(frames, pts)):
        e = write_ease[i] if i < len(write_ease) else EASE_OUT
        pos.append((f, list(p), e))
        trim_e.append((f, 100 * cum[i] / total, e if i < len(pts) - 1 else "hold"))
    pos += [(104, list(pts[-1]), EASE), (134, rest, None)]
    pos[len(frames) + 1] = (frames[-1], list(pts[-1]), "hold")
    trim_e += [(160, 100, "hold"), (161, 0, None)]
    rot = anim([(0, 28, "hold"), (18, 28, EASE), (44, 30, EASE), (54, 25, EASE),
                (64, 31, EASE), (74, 25, EASE), (84, 31, EASE), (94, 27, EASE),
                (104, 27, EASE), (134, 28, None)])
    line_o = anim([(0, 100, "hold"), (138, 100, EASE), (158, 0, "hold"), (161, 0, "hold"),
                   (162, 100, None)])

    line3 = group("line3", [
        path(pts, closed=False), trim(anim(trim_e)), stroke(BLUE, 24, cap=2, join=2),
    ], xform(o=line_o))
    lines = group("lines", [
        path([(160, 202), (330, 202)], closed=False),
        path([(160, 264), (300, 264)], closed=False),
        stroke(BLUE, 24),
    ])
    pen = group("pen", [
        solid("lead", path([(-8, -17), (8, -17), (0, 0)]), INK, outline=0),
        solid("tip", path([(-24, -52), (24, -52), (0, 0)]), WHITE, outline=14),
        solid("cap", rect(0, -262, 48, 26, 6), WHITE, outline=14),
        solid("barrel", rect(0, -152, 48, 200, 6), BLUE, outline=14),
    ], xform(p=anim(pos), a=(0, 0), r=rot))
    corner = solid("corner", path([(330, 64), (330, 126), (392, 126)]), BLUE, outline=12)
    sheet = solid("sheet", path([(120, 64), (330, 64), (392, 126), (392, 448), (120, 448)]),
                  WHITE)
    return document("Личные заметки", [pen, line3, lines, corner, sheet])


ICONS = {
    "navigation": compass,
    "projects": projects,
    "business": business,
    "notes": notes,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "build", "lottie"))
    ap.add_argument("--tgs", default=os.path.join(HERE, "..", "tgs"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.tgs, exist_ok=True)
    for name, fn in ICONS.items():
        data = json.dumps(fn(), ensure_ascii=False, separators=(",", ":"))
        with open(os.path.join(a.out, name + ".json"), "w") as f:
            f.write(data)
        with gzip.GzipFile(os.path.join(a.tgs, name + ".tgs"), "wb", mtime=0) as f:
            f.write(data.encode())
        print(f"{name}: {len(data)} B json")


if __name__ == "__main__":
    main()
