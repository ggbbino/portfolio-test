#!/usr/bin/env python3
"""Sound design for the Plates film — synthesised, no samples, no licences needed.

    python3 src/sfx.py   -> build/sfx.wav (stereo 48 kHz, 28 s)
                            build/click_120bpm.wav (beat guide for laying music, not in the film)

Every event sits on the same 120 BPM grid as the picture (beat = 0.5 s), so a
minimal-techno / cinematic-electronic track at 120 BPM drops in with its downbeat
at 0:00 (or 0:03 for the kick entry) and all hits line up.
"""
import os
import wave

import numpy as np

SR = 48000
DUR = 28.0
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
rng = np.random.default_rng(11)
N = int(SR * DUR)
mix = np.zeros((N, 2), np.float32)


def t_axis(d):
    return np.arange(int(SR * d)) / SR


def place(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if sig.ndim == 1:
        l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
        sig = np.stack([sig * l * 1.414, sig * r * 1.414], 1)
    j = min(N, i + len(sig))
    mix[i:j] += gain * sig[: j - i]


def svf(x, fc, q=0.7, mode="bp"):
    """Chamberlin state-variable filter; fc may be an array (sweeps)."""
    fc = np.broadcast_to(np.asarray(fc, np.float64), x.shape)
    low = band = 0.0
    out = np.empty_like(x)
    damp = 1.0 / q
    for n in range(len(x)):
        f = 2 * np.sin(np.pi * min(fc[n], SR / 6) / SR)
        high = x[n] - low - damp * band
        band += f * high
        low += f * band
        out[n] = band if mode == "bp" else low if mode == "lp" else high
    return out


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for n in range(len(x)):
        acc = (1 - a) * x[n] + a * acc
        y[n] = acc
    return y


def noise(d):
    return rng.standard_normal(int(SR * d)).astype(np.float64)


def env_ad(d, a, decay):
    t = t_axis(d)
    return np.minimum(t / max(a, 1e-4), 1) * np.exp(-np.maximum(t - a, 0) / decay)


def sub_hit(f0=68, f1=38, d=1.2, decay=0.38):
    t = t_axis(d)
    f = f1 + (f0 - f1) * np.exp(-t / 0.09)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env_ad(d, 0.004, decay)
    click = lowpass(noise(0.03), 1800) * env_ad(0.03, 0.001, 0.008)
    out = body
    out[: len(click)] += 0.6 * click
    return out


def whoosh(d, f_from, f_to, q=1.2):
    t = t_axis(d)
    fc = f_from * (f_to / f_from) ** (t / d)
    s = svf(noise(d), fc, q)
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    return s * e


def riser(d, f_from=300, f_to=5000):
    t = t_axis(d)
    fc = f_from * (f_to / f_from) ** ((t / d) ** 1.6)
    s = svf(noise(d), fc, 2.0)
    e = (t / d) ** 2.4
    e[-int(0.006 * SR):] *= np.linspace(1, 0, int(0.006 * SR))
    tone = np.sin(2 * np.pi * np.cumsum(220 * 4 ** ((t / d) ** 2)) / SR) * 0.15
    return (s + tone) * e


def ui_click(f=2400, d=0.05):
    t = t_axis(d)
    return (np.sin(2 * np.pi * f * t) * 0.6 + svf(noise(d), 5000, 3)) * env_ad(d, 0.0008, 0.010)


def blip(f0=1300, f1=1650, d=0.12):
    t = t_axis(d)
    f = f0 + (f1 - f0) * np.minimum(t / 0.04, 1)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(d, 0.003, 0.035)


def reverb(x, seconds=2.0, wet=0.18):
    ir_n = int(SR * seconds)
    ir = rng.standard_normal((ir_n, 2)) * np.exp(-np.arange(ir_n) / (SR * seconds / 6.5))[:, None]
    ir[:, 0] = lowpass(ir[:, 0], 6000)
    ir[:, 1] = lowpass(ir[:, 1], 6000)
    ir /= np.sqrt((ir ** 2).sum(0))
    n = len(x) + ir_n
    nfft = 1 << (n - 1).bit_length()
    out = np.zeros((len(x), 2))
    for c in range(2):
        y = np.fft.irfft(np.fft.rfft(x[:, c], nfft) * np.fft.rfft(ir[:, c], nfft), nfft)[: len(x)]
        out[:, c] = y
    return x * (1 - wet) + out * wet * 3


# ---------------------------------------------------------------- events
# 0–3 s: dark air + low drone, riser into the reveal
d = 3.05
t = t_axis(d)
drone = (np.sin(2 * np.pi * 49 * t) * 0.55 + np.sin(2 * np.pi * 98 * t) * 0.18) * np.minimum(t / 1.4, 1)
air = svf(noise(d), 1400, 0.6) * 0.10 * np.minimum(t / 1.0, 1)
place((drone + air) * (1 - np.clip((t - 2.9) / 0.15, 0, 1)), 0.0, 0.32)
place(riser(1.3), 1.70, 0.22)

place(sub_hit(70, 38, 1.6, 0.45), 3.0, 0.95)                    # reveal
place(lowpass(noise(1.6), 900) * env_ad(1.6, 0.01, 0.5), 3.0, 0.10)
place(sub_hit(62, 40, 0.8, 0.22), 6.0, 0.5)                      # zoom in
place(whoosh(0.7, 500, 2600, 1.0), 5.65, 0.10)
place(ui_click(2600), 6.62, 0.22, pan=-0.2)                      # cards settle
for at, f in ((10.0, 62), (11.0, 58), (12.0, 54)):               # 60 / 55 / 50
    place(sub_hit(f, 36, 1.0, 0.30), at, 0.85)
    place(svf(noise(0.25), 1200, 1.5) * env_ad(0.25, 0.002, 0.05), at, 0.12)
place(riser(0.7, 400, 3000), 12.6, 0.12)                        # into the match cut
place(ui_click(3100, 0.04), 13.70, 0.30)                          # «50» lands in its field
place(whoosh(0.55, 3200, 500, 1.4), 13.98, 0.26)                  # swipe to Прогресс
place(blip(), 16.32, 0.16, pan=0.25)                              # chart end point
place(ui_click(2200), 17.47, 0.28, pan=-0.1)                      # tap on the picker
place(whoosh(0.3, 1800, 3500, 2.0), 17.55, 0.06)
place(sub_hit(60, 40, 0.8, 0.25), 18.0, 0.45)
for at, d in ((18.82, 0.6), (19.97, 0.6), (21.12, 0.85)):         # montage whips
    place(whoosh(d, 700, 3000, 1.1), at, 0.20, pan=0.3)
# final shot: soft hit + a quiet held pad that fades into the black
place(sub_hit(55, 38, 1.4, 0.5), 22.0, 0.55)
d = 3.0
t = t_axis(d)
pad = (np.sin(2 * np.pi * 110 * t) + 0.6 * np.sin(2 * np.pi * 164.8 * t) + 0.4 * np.sin(2 * np.pi * 220.4 * t))
pad = lowpass(pad, 900) * np.minimum(t / 0.8, 1) * (1 - np.clip((t - 2.2) / 0.8, 0, 1)) ** 2
place(pad * 0.06 + svf(noise(d), 2500, 0.7) * 0.025 * np.minimum(t / 0.8, 1) * (1 - t / d), 22.0, 1.0)
# brand: one gentle, deep hit with a long tail
place(sub_hit(52, 34, 2.6, 0.9), 25.45, 0.5)
place(svf(noise(2.5), 700, 0.8) * env_ad(2.5, 0.05, 0.7), 25.45, 0.06)

mix = reverb(mix.astype(np.float64), 2.0, 0.16)
mix[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))[:, None]
mix /= max(1e-9, np.abs(mix).max()) / 0.85


def write(path, x):
    x = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())


os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
write(os.path.join(ROOT, "build", "sfx.wav"), mix)

# beat guide: 120 BPM, accent on every bar (2 s), for laying music only
g = np.zeros((N, 2))
for k in range(int(DUR * 2)):
    c = ui_click(1800 if k % 4 == 0 else 1200, 0.03)
    i = int(k * 0.5 * SR)
    g[i:i + len(c)] += (0.6 if k % 4 == 0 else 0.3) * c[:, None]
write(os.path.join(ROOT, "build", "click_120bpm.wav"), g)
print("sfx.wav + click_120bpm.wav written")
