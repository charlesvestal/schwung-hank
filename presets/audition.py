#!/usr/bin/env python3
"""Render every preset in bank.json through the CURRENT engine and describe it.

Re-authoring a bank by ear alone is slow and misses the failures that matter
most -- a preset that is silent, or clipping, or 20 dB off its neighbours.
These are the things a number catches and an ear catches late, so they get
caught first and the ear is spent on whether the sound is any good.

Renders exactly what the device plays: the same engine-unit conversion
gen_presets.py compiles into the C table.

  peak/rms   level, in dBFS. ~-20 dBFS rms is a healthy module level.
  centroid   brightness, Hz.
  t60        time to fall 60 dB from the peak -- how long the note actually is.
  harm       share of energy on harmonics of the played note; low = noisy.
"""
import json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN  = os.path.join(ROOT, "build", "hank_render")
DSO  = os.path.join(ROOT, "build", "dsp_native.so")
SR   = 44100
NOTE = int(os.environ.get("AUDITION_NOTE", "60"))
F0   = 440.0 * 2 ** ((NOTE - 69) / 12.0)

# Reuse gen_presets' own FIELDS table rather than restating it: a second copy
# of the display->engine conversion would drift from the one that is compiled.
import importlib.util as _il
_sp = _il.spec_from_file_location("genp", os.path.join(HERE, "gen_presets.py"))
_g = _il.module_from_spec(_sp)
import io, contextlib
_old = sys.argv[:]; sys.argv = ["gen_presets.py"]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        _sp.loader.exec_module(_g)          # regenerates the header; same content
except SystemExit:
    pass
finally:
    sys.argv = _old
FIELDS = _g.FIELDS

bank = json.load(open(os.path.join(HERE, "bank.json")))
d = bank["_defaults"]

# gen_presets' first column names the C TABLE's field (PF_OP1_S), which is not
# the engine's set_param key (op1_sustain). Using it directly meant every render
# silently fell back to defaults and all 32 presets measured identical -- the
# probe was describing the default patch 32 times.
PARAM_KEY = {}   # macro names are the engine keys now

def engine_args(p):
    out = []
    for ekey, bkey, conv in FIELDS:
        out.append(f"{PARAM_KEY.get(ekey, ekey)}={conv(p.get(bkey, d[bkey]))}")
    return out

def render(p, secs=3.0, gate=1.5):
    r = subprocess.run([BIN, DSO, str(secs), str(gate), str(NOTE)] + engine_args(p),
                       capture_output=True, check=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x[:len(x)//2*2].reshape(-1, 2)

def describe(st):
    mono = st.mean(axis=1)
    pk = float(np.max(np.abs(mono)))
    # RMS OF THE BODY, not of the render. Averaging a 60 ms kick over 3 s of
    # silence reports -49 dBFS and flags it as broken; the ear hears its
    # loudness, not its duty cycle. The body is everything within 20 dB of peak.
    k0 = 512
    env0 = np.sqrt(np.convolve(mono*mono, np.ones(k0)/k0, "same"))
    body = mono[env0 > env0.max() * 0.1] if env0.max() > 0 else mono
    rms = float(np.sqrt(np.mean(body*body))) if body.size else 0.0
    db = lambda v: 20*np.log10(max(v, 1e-12))
    k = 512
    e = np.sqrt(np.convolve(mono*mono, np.ones(k)/k, "same"))
    t60 = float("nan")
    if e.max() > 1e-7:
        i0 = int(np.argmax(e)); thr = e[i0] * 1e-3
        below = np.where(e[i0:] < thr)[0]
        t60 = (below[0] / SR) if len(below) else float("nan")
    # Brightness is measured from the ATTACK, where an FM patch's modulator is
    # still alive. Windowing at 50 ms missed it entirely on every plucked preset
    # and reported the bare fundamental.
    w = mono[:int(0.25*SR)]
    cen = harm = float("nan")
    if w.size > 1024 and np.max(np.abs(w)) > 1e-7:
        S = np.abs(np.fft.rfft(w*np.hanning(w.size))); fr = np.fft.rfftfreq(w.size, 1/SR)
        pw = S*S
        # IGNORE BELOW 20 Hz. It is not audible pitch, and any DC the shaper
        # has not finished blocking would otherwise drag the centroid to ~1 Hz
        # and report a bright patch as having no brightness at all.
        pw[fr < 20.0] = 0.0
        tot = pw.sum()+1e-30
        cen = float((fr*pw).sum()/tot)
        on = np.zeros(len(fr), bool)
        for kk in range(1, 60): on |= np.abs(fr - kk*F0) < 15.0
        harm = float(100*pw[on].sum()/tot)
    return db(pk), db(rms), cen, t60, harm

rows = []
for p in bank["presets"]:
    sus = p.get("sustain", d.get("sustain", 0.0))
    rows.append((p["name"], p["cat"]) + describe(render(p)) + (sus,))

# ACROSS THE KEYBOARD. A preset that only works at middle C is a bad preset, and
# the single-note view cannot see it: with keytracking the filter rides up with
# the note, and a high operator ratio walks the modulator into the rolloff. Both
# thin a patch out at the top of the range while C4 still measures fine.
spread = []
for p in bank["presets"]:
    pks = []
    for nn in (36, 48, 60, 72, 84):
        globals()["NOTE"] = nn
        st = render(p)
        m2 = st.mean(axis=1)
        pks.append(20*np.log10(max(float(np.max(np.abs(m2))), 1e-12)))
    globals()["NOTE"] = int(os.environ.get("AUDITION_NOTE", "60"))
    spread.append((max(pks) - min(pks), p["name"], pks))

print(f"note {NOTE} ({F0:.0f} Hz), 1.5 s gate in a 3 s render\n")
print(f"  {'preset':16s} {'cat':6s} {'peak':>7} {'rms':>7} {'cen Hz':>8} {'t60 s':>7} {'harm%':>7}  flags")
bad = 0
for n, c, pk, rms, cen, t60, harm, sus in rows:
    f = []
    if pk < -60: f.append("SILENT")
    elif pk < -28: f.append("quiet")
    if pk > -1.0: f.append("CLIPPING")
    if t60 == t60 and t60 < 0.05: f.append("ultra short")
    # A sustaining patch is MEANT to hold; only a preset with no sustain that
    # never decays is broken. Flagging every pad taught nothing and buried the
    # one preset that was actually wrong.
    if t60 != t60 and sus < 0.05: f.append("never decays")
    if f: bad += 1
    print(f"  {n:16s} {c:6s} {pk:7.1f} {rms:7.1f} {cen:8.0f} {t60:7.2f} {harm:7.1f}  {' '.join(f)}")
lv = np.array([r[3] for r in rows]); pkv = np.array([r[2] for r in rows])
bx = np.array([r[4] for r in rows if r[4] == r[4]]) / F0
print(f"  brightness x f0   min {bx.min():.1f}  median {np.median(bx):.1f}  "
      f"max {bx.max():.1f}   above 10x: {(bx > 10).sum()} of {len(bx)}")
print(f"\n  body rms {lv.min():.1f} .. {lv.max():.1f} dBFS (median {np.median(lv):.1f}, spread {lv.max()-lv.min():.1f})")
print(f"  peak     {pkv.min():.1f} .. {pkv.max():.1f} dBFS (spread {pkv.max()-pkv.min():.1f});  {bad} flagged")
spread.sort(reverse=True)
worst = [s for s in spread if s[0] > 12.0]
if worst:
    print("\n  UNEVEN ACROSS THE KEYBOARD (peak dB at notes 36/48/60/72/84):")
    for d, n, pks in worst:
        print(f"    {n:16s} spread {d:5.1f} dB   " + " ".join(f"{v:6.1f}" for v in pks))
else:
    print("\n  every preset within 12 dB across notes 36..84")
cen = np.array([r[4] for r in rows])
dull = [r[0] for r in rows if r[4] == r[4] and r[4] < 1.6*F0]
if dull: print(f"  centroid at the fundamental (no FM brightness): {', '.join(dull)}")
