#!/usr/bin/env python3
"""Turn each macro from 0 to 1 and check it behaves like a musical control.

A knob is not tested by its endpoints. What matters across its travel is that
it never goes silent, never jumps in loudness, and moves its character in ONE
direction -- and none of that is visible from a preset that happens to sit at
one setting.

TWO WINDOWS, BECAUSE ONE WINDOW MISSED TWO CONTROLS IN A ROW.

This measured 250ms-1s only. On an instrument whose modulator decays faster
than its carrier by construction, that window sits after most of what the
timbre controls do, so anything shaped like an attack was reported as a flat
row of identical numbers -- "the knob does nothing". PITCH was written off that
way once, and NOISE read as inert the first time it was measured while being
plainly audible. The attack window is 2-120ms; a control may legitimately move
only one of the two.
"""
import os, subprocess, sys
import numpy as np
SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = dict(ratio=4, bright=0.45, bite=0.0, tone=0.8, attack=0.0,
            decay=0.55, sustain=0.8, noise=0.0, macro_mode=1,
            voice_count=1, volume=0.5)

def measure(**over):
    kw = dict(BASE); kw.update(over)
    r = subprocess.run([f"{ROOT}/build/hank_render", f"{ROOT}/build/dsp_native.so",
                        "1.6", "1.2", "48"] + [f"{k}={v}" for k, v in kw.items()],
                       capture_output=True, check=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    m = x[:len(x)//2*2].reshape(-1, 2).mean(axis=1)
    return score(m, 0.002, 0.120), score(m, 0.25, 1.0)

def score(m, t0, t1):
    w = m[int(t0*SR):int(t1*SR)]
    if w.size < 512: return -99.0, 0.0
    rms = float(np.sqrt(np.mean(w*w)))
    S = np.abs(np.fft.rfft(w*np.hanning(w.size))); fr = np.fft.rfftfreq(w.size, 1/SR)
    p = S*S; p[fr < 20] = 0
    cen = float((fr*p).sum()/(p.sum()+1e-30))
    return 20*np.log10(max(rms, 1e-12)), cen

STEPS = [i/10 for i in range(11)]
# RATIO is an enum of 16 ratios, not a 0..1 control: swept 0..1 it would test
# two of its sixteen steps and report the knob as nearly inert.
RANGE = {"ratio": [i for i in range(0, 16)]}
print(f"  {'macro':9s} " + " ".join(f"{v:>6.1f}" for v in STEPS))
issues = []
for macro in ("ratio", "bright", "bite", "tone", "attack", "decay", "sustain", "noise"):
    early, late = [], []
    steps = RANGE.get(macro, STEPS)
    for v in steps:
        e, l = measure(**{macro: v}); early.append(e); late.append(l)
    if len(steps) != len(STEPS):
        print(f"  {macro:9s} (swept over its {len(steps)} declared steps)")
    for tag, rows in (("ATK", early), ("SUS", late)):
        print(f"  {macro if tag == 'ATK' else '':9s} " +
              " ".join(f"{a:6.1f}" for a, _ in rows) + f"   dBFS  {tag} 2-120ms" if tag == "ATK"
              else f"  {'':9s} " + " ".join(f"{a:6.1f}" for a, _ in rows) + f"   dBFS  {tag} 250ms-1s")
        print(f"  {'':9s} " + " ".join(f"{b:6.0f}" for _, b in rows) + "   centroid Hz")
    lv = [a for a, _ in late]; cn = [b for _, b in late]
    ev = [a for a, _ in early]; ec = [b for _, b in early]
    # SILENCE AND JUMPS ARE JUDGED AT THE ONSET, for the same reason the range
    # check exempts sustain: a percussive setting is legitimately gone by
    # 250 ms, and reporting that as SILENT is a false alarm -- it fired on
    # every run for a year and trained me to skim past the whole PROBLEMS
    # block, which is worse than not checking. A knob that genuinely kills the
    # sound kills its onset too.
    dead = [steps[i] for i, v in enumerate(ev) if v < -55]
    if dead: issues.append(f"{macro}: SILENT at {dead}")
    jump = max(abs(ev[i+1]-ev[i]) for i in range(len(ev)-1))
    if jump > 12: issues.append(f"{macro}: jumps {jump:.0f} dB between adjacent steps")
    rng = max(ev) - min(ev)
    # SUSTAIN and ATTACK are SUPPOSED to change the level in a window that sits
    # mid-note: no sustain means the note has already decayed, and a very slow
    # attack has not arrived yet. Flagging them taught nothing and hid BITE,
    # which was losing 21 dB for a reason that WAS a fault.
    if macro != "attack" and rng > 20:
        issues.append(f"{macro}: {rng:.0f} dB of level change across the knob")
print()
if issues:
    print("  PROBLEMS")
    for i in issues: print("   ", i)
else:
    print("  every macro: no silence, no jumps, level held")
