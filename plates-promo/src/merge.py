#!/usr/bin/env python3
"""Merge motion-blur sub-frames (f_XXXX_sK.png) into f_XXXX.png."""
import glob, os, re, sys
import numpy as np
from PIL import Image

d = sys.argv[1]
groups = {}
for p in glob.glob(os.path.join(d, "f_*_s*.png")):
    groups.setdefault(re.sub(r"_s\d+\.png$", ".png", p), []).append(p)
for out, parts in groups.items():
    acc = sum(np.asarray(Image.open(p).convert("RGB")).astype(np.float32) for p in parts)
    Image.fromarray(np.clip(acc / len(parts) + 0.5, 0, 255).astype(np.uint8)).save(out)
    for p in parts:
        os.remove(p)
print(f"merged {len(groups)} motion-blurred frames")
