#!/usr/bin/env python3
"""Render a palette of candidate saturators for BITE, to choose by ear.

The distortion network deleted in the redesign sounded excellent, so the
replacement has a bar to clear. Rather than argue about curves, apply each
candidate to REAL FM output from our own engine (distortion off) and listen.
Offline, so no engine change is needed to hear them.

The shapers that matter for an FM synth are the ones that add what FM does not
already have. FM makes rich ODD harmonics on its own, so a symmetric odd-order
curve -- tanh, cubic -- mostly adds more of what is there. Asymmetry (even
harmonics) and folding (harmonics that are not a smooth extension of the input)
are the ones that change the sound rather than thicken it.
"""
import os, struct, subprocess, sys
import numpy as np
SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

def dry(**kw):
    """A note from our own engine, distortion off."""
    note = kw.pop("note", 48)          # a render argument, not an engine param
    base = dict(op2_level=0.45, op2_coarse=2, op2_fine=0, op2_fbk=0.25,
                op2_attack=0, op2_decay=0.45, op2_sustain=0.55, op2_release=0.4,
                op1_attack=0, op1_decay=0.5, op1_sustain=0.75, op1_release=0.4,
                filter_on=0, cutoff=1, resonance=0, filter_mix=0, filter_env=0,
                distortion=0, unison=0, width=0, crush=0, volume=0.5, voice_count=1)
    base.update(kw)
    args = [f"{k}={v}" for k, v in base.items()]
    r = subprocess.run([f"{ROOT}/build/hank_render", f"{ROOT}/build/dsp_native.so",
                        "2.4", "1.6", str(note)] + args,
                       capture_output=True, check=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x[:len(x)//2*2].reshape(-1, 2).mean(axis=1)

def dcblock(x, pole=0.9995):
    y = np.empty_like(x); px = py = 0.0
    for i, v in enumerate(x):
        py = (v - px) + pole*py; px = v; y[i] = py
    return y

# ---- the candidates -------------------------------------------------------
# ROUND 2. Folding and foldback were rejected as too metallic; the asymmetric,
# even-harmonic family is the direction. All six below are in that family and
# differ in HOW the asymmetry is produced, which is what changes the flavour.
#
# The round-1 "rectify" under-delivered and was described as octave-up when it
# was not: |x| carried only 0.275 weight and then went through tanh, which
# squashed the very thing that makes an octave. `octave` below does it properly.

def s_tube_mild(x, d):   # gentle asymmetry: soft one way, slightly harder the other
    g = (1 + 12*d) * x
    return dcblock(np.where(g >= 0, np.tanh(g), np.tanh(g*1.3)/1.3))

def s_tube_strong(x, d): # the same idea pushed -- more even content, more "amp"
    g = (1 + 12*d) * x
    return dcblock(np.where(g >= 0, np.tanh(g), np.tanh(g*2.4)/2.4))

def s_bias(x, d):        # the classic tube move: offset, saturate, remove the DC.
    g = (1 + 12*d) * x   # bias grows with drive, so evens come in as it is pushed
    b = 0.9 * d
    return dcblock(np.tanh(g + b) - np.tanh(b))

def s_octave(x, d):      # a REAL rectifier blend: |x| before the saturator, not after
    g = (1 + 7*d) * x
    rect = 2.0*np.abs(g) - 1.0
    return dcblock(np.tanh((1.0 - 0.7*d)*g + 0.7*d*rect))

def s_diode(x, d):       # exponential one way, near-linear the other
    g = (1 + 10*d) * x
    return dcblock(np.where(g >= 0, 1.0 - np.exp(-g), -(1.0 - np.exp(-0.45*(-g)))/0.45))

def s_tube_soft(x, d):   # asymmetry, then a symmetric limit -- two stages, like an amp
    g = (1 + 10*d) * x
    a = dcblock(np.where(g >= 0, np.tanh(g), np.tanh(g*1.8)/1.8))
    return np.tanh(1.4*a)

SHAPERS = [("1_tube_mild", s_tube_mild), ("2_tube_strong", s_tube_strong),
           ("3_bias", s_bias), ("4_octave", s_octave),
           ("5_diode", s_diode), ("6_tube_soft", s_tube_soft)]

SOURCES = [("bass",  dict(op2_coarse=2,   op2_level=0.45, note=36)),
           ("keys",  dict(op2_coarse=4,   op2_level=0.40, note=48)),
           ("bell",  dict(op2_coarse=7,   op2_level=0.45, op2_fbk=0.10, note=55))]

def wav(path, mono):
    st = np.repeat(np.clip(mono, -1, 1)[:, None], 2, axis=1)
    b = (st*32767).astype('<i2').tobytes()
    with open(path, 'wb') as f:
        f.write(b'RIFF'+struct.pack('<I', 36+len(b))+b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, 2, SR, SR*4, 4, 16))
        f.write(b'data'+struct.pack('<I', len(b))+b)

print("rendering", len(SHAPERS), "shapers x", len(SOURCES), "sources x 3 drives\n")
report = []
for sname, skw in SOURCES:
    d0 = dry(**skw)
    peak = np.max(np.abs(d0)) + 1e-12
    wav(os.path.join(OUT, f"{sname}_0_dry.wav"), d0/peak*0.7)
    for fname, fn in SHAPERS:
        parts = []
        for drv in (0.25, 0.55, 0.9):
            y = fn(d0/peak, drv)
            y = y / (np.max(np.abs(y)) + 1e-12) * 0.7      # normalise: judge TONE, not level
            parts.append(y)
            # odd/even harmonic split at the played note
            f0 = 440*2**((skw.get("note", 48)-69)/12)
            w = y[int(0.2*SR):int(0.2*SR)+SR//2]
            S = np.abs(np.fft.rfft(w*np.hanning(w.size))); fr = np.fft.rfftfreq(w.size, 1/SR)
            p = S*S
            odd = sum(p[np.abs(fr-k*f0) < 12].sum() for k in range(1, 40, 2))
            even = sum(p[np.abs(fr-k*f0) < 12].sum() for k in range(2, 40, 2))
            if drv == 0.55:
                report.append((sname, fname, 10*np.log10(max(even, 1e-30)/max(odd, 1e-30)),
                               float((fr*p).sum()/(p.sum()+1e-30))))
        wav(os.path.join(OUT, f"{sname}_{fname}.wav"),
            np.concatenate([np.concatenate([p, np.zeros(int(0.25*SR))]) for p in parts]))
print(f"  {'source':7s} {'shaper':14s} {'even/odd dB':>12} {'centroid':>9}")
for s, f, eo, cen in report:
    print(f"  {s:7s} {f:14s} {eo:12.1f} {cen:9.0f}")
print(f"\n{len(os.listdir(OUT))} files in {OUT}")
print("each shaper file: drive 25%, 55%, 90% with gaps; *_0_dry.wav is unshaped")
