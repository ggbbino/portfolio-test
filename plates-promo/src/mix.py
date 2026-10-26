#!/usr/bin/env python3
"""Final audio: music bed (BerryDeep — Minimal Techno, 29 s cut) + quiet SFX.

    python3 src/mix.py <music.mp3>   -> build/mix.wav  (-14 LUFS integrated, TP ≤ -1 dBTP)

* music starts at 0:00 with a short 0.3 s fade-in (the cut starts mid-phrase)
* SFX sit ~13 LU under the music
* the music tails out naturally under the logo: equal-power fade 26.6 → 29.0 s
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SR, DUR = 48000, 29.0
N = int(SR * DUR)


def decode(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    out = np.zeros((N, 2))
    out[:min(N, len(x))] = x[:N]
    return out


def write(path, x):
    x = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x.tobytes())


def lufs(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "loudnorm=print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return json.loads(err[err.rindex("{"):err.rindex("}") + 1])


music = decode(sys.argv[1])
sfx = decode(os.path.join(ROOT, "build", "sfx.wav"))
t = np.arange(N) / SR
env = np.clip(t / 0.3, 0, 1)                                           # fade-in
fo = np.clip((t - 26.6) / (DUR - 26.6), 0, 1)
env *= np.cos(fo * np.pi / 2)                                          # equal-power tail
music *= env[:, None]

tmp = os.path.join(ROOT, "build")
write(os.path.join(tmp, "_m.wav"), music * 0.5)
write(os.path.join(tmp, "_s.wav"), sfx * 0.5)
lm, ls = float(lufs(os.path.join(tmp, "_m.wav"))["input_i"]), float(lufs(os.path.join(tmp, "_s.wav"))["input_i"])
gain = 10 ** (((lm - 13.0) - ls) / 20)                                 # SFX 13 LU under the music
mixed = music + sfx * gain
write(os.path.join(tmp, "_pre.wav"), mixed * 0.5)

# two-pass loudnorm (linear) → -14 LUFS, true peak ≤ -1 dBTP
m = lufs(os.path.join(tmp, "_pre.wav"))
af = (f"loudnorm=I=-14:TP=-1.0:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", os.path.join(tmp, "_pre.wav"), "-af", af,
                "-ar", str(SR), os.path.join(tmp, "mix.wav")], check=True)
for f in ("_m.wav", "_s.wav", "_pre.wav"):
    os.remove(os.path.join(tmp, f))
r = lufs(os.path.join(tmp, "mix.wav"))
print(f"music {lm:.1f} LUFS(-6 dB), sfx gain {20*np.log10(gain):.1f} dB -> mix {r['input_i']} LUFS, TP {r['input_tp']} dBTP")
