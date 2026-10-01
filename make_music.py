#!/usr/bin/env python3
"""
make_music.py — placeholder cinematic music + SFX generator.

The build environment has no internet, so this synthesises a temporary
cinematic/mystery bed and transition SFX with numpy. The mood is chosen to
fit a science-mystery video (dark ambient pad + heartbeat tension + soft
bells). Replace the files in brand/music/ and brand/sfx/ with real
royalty-free tracks when available (see brand/README.md). Gitignored.
"""

import os
import wave

import numpy as np

SR = 44100
REPO = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(REPO, "brand", "music")
SFX_DIR = os.path.join(REPO, "brand", "sfx")

# D minor colour palette
D, F, G, A, C = 146.83, 174.61, 196.00, 220.00, 261.63


def bell(freq, dur=1.6, amp=0.16):
    """Soft sine bell with long decay."""
    t = np.arange(int(SR * dur)) / SR
    w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    return amp * w * np.exp(-t * 2.2)


def heartbeat(dur=0.5):
    """Two-thump heartbeat pulse for mystery tension."""
    t = np.arange(int(SR * dur)) / SR
    f = 62 * np.exp(-t * 7) + 42
    ph = 2 * np.pi * np.cumsum(f) / SR
    thump = np.sin(ph) * np.exp(-t * 9)
    echo = np.roll(thump, int(0.16 * SR)) * 0.5
    echo[: int(0.16 * SR)] = 0
    return 0.8 * (thump + echo)


def add(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[: j - i]


def cinematic_bed(seconds=180.0, seed=11):
    """Dark ambient bed: D-minor pad + slow swells + heartbeat + sparse bells."""
    rng = np.random.default_rng(seed)
    buf = np.zeros(int(SR * seconds))

    # pad: D minor triad, each voice with its own slow tremolo for movement
    t = np.arange(int(SR * seconds)) / SR
    for freq, lfo_hz, amp in ((D, 0.50, 0.07), (F, 0.23, 0.05),
                              (A, 0.11, 0.045), (D * 2, 0.31, 0.03)):
        trem = 1 + 0.35 * np.sin(2 * np.pi * lfo_hz * t)
        buf += amp * trem * np.sin(2 * np.pi * freq * t)

    # heartbeat pulse every 2 beats (~72 bpm)
    beat = 60.0 / 72.0
    t_beat = 0.5
    while t_beat < seconds - 1:
        add(buf, heartbeat(), t_beat)
        t_beat += 2 * beat

    # sparse bells on the minor palette
    scale = [D, F, G, A, C, D * 2]
    t_bell = 2.0
    while t_bell < seconds - 2:
        add(buf, bell(scale[int(rng.integers(0, len(scale)))]), t_bell)
        t_bell += float(rng.uniform(2.0, 5.0))

    peak = np.max(np.abs(buf)) + 1e-9
    return 0.55 * buf / peak


def whoosh(dur=0.9):
    """Cinematic transition whoosh: swept lowpassed noise."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = np.random.default_rng(3).standard_normal(n)
    cut = 0.04 + 0.38 * np.sin(np.pi * t / dur)
    y, prev = np.zeros(n), 0.0
    for i in range(n):
        prev += cut[i] * (noise[i] - prev)
        y[i] = prev
    y /= np.max(np.abs(y)) + 1e-9
    return 0.8 * y * np.sin(np.pi * t / dur) ** 1.5


def riser(dur=2.5):
    """Suspense riser for the hook."""
    t = np.arange(int(SR * dur)) / SR
    f = 180 * (1 + 9 * t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * (t / dur) ** 1.5
    y += np.random.default_rng(5).standard_normal(len(t)) * (t / dur) * 0.15
    y /= np.max(np.abs(y)) + 1e-9
    return 0.7 * y


def impact(dur=1.2):
    """Soft low impact for the final reveal."""
    t = np.arange(int(SR * dur)) / SR
    f = 70 * np.exp(-t * 6) + 40
    ph = 2 * np.pi * np.cumsum(f) / SR
    return 0.9 * np.sin(ph) * np.exp(-t * 5)


def write_wav(path, buf):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = (np.clip(buf, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"  wrote {os.path.relpath(path, REPO)}  ({len(buf) / SR:.1f}s)")


def main():
    print("== generating placeholder cinematic assets ==")
    write_wav(os.path.join(MUSIC_DIR, "placeholder-cinematic-bed.wav"), cinematic_bed(180))
    write_wav(os.path.join(SFX_DIR, "placeholder-whoosh.wav"), whoosh())
    write_wav(os.path.join(SFX_DIR, "placeholder-riser.wav"), riser())
    write_wav(os.path.join(SFX_DIR, "placeholder-impact.wav"), impact())
    print("  (replace with real royalty-free tracks from brand/README.md)")


if __name__ == "__main__":
    main()
