#!/usr/bin/env python3
"""BITE: tube asymmetry with the octave arriving as the knob is pushed.

Chosen by ear from shaper_palette round 2 -- tube warmth plus a rectifier,
which Charles liked but found too intense. So the SHAPE is settled and the one
open number is how much octave arrives at full travel. This varies only that,
so the choice is a single judgement rather than six.

The rectified copy is blended into the signal BEFORE the asymmetric saturator,
not after: putting it after is what made round 1's version fail to sound like
an octave at all.
"""
import os, struct, subprocess, sys
import numpy as np
SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)

def dcblock(x, pole=0.9995):
    y = np.empty_like(x); px = py = 0.0
    for i, v in enumerate(x):
        py = (v - px) + pole*py; px = v; y[i] = py
    return y

def dry(note, **kw):
    base = dict(op2_level=0.45, op2_coarse=2, op2_fine=0, op2_fbk=0.15,
                op2_attack=0, op2_decay=0.45, op2_sustain=0.55, op2_release=0.4,
                op1_attack=0, op1_decay=0.5, op1_sustain=0.75, op1_release=0.4,
                filter_on=0, cutoff=1, resonance=0, filter_mix=0, filter_env=0,
                distortion=0, unison=0, width=0, crush=0, volume=0.5, voice_count=1)
    base.update(kw)
    r = subprocess.run([f"{ROOT}/build/hank_render", f"{ROOT}/build/dsp_native.so",
                        "2.4", "1.6", str(note)] + [f"{k}={v}" for k, v in base.items()],
                       capture_output=True, check=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x[:len(x)//2*2].reshape(-1, 2).mean(axis=1)

def bite(x, d, oct_max):
    """d is the knob, 0..1. Tube asymmetry always; the octave arrives with d.

    Two things here were wrong in the first version and are worth stating,
    because both are easy to get wrong again:

    ASYMMETRIC RAILS, NOT ASYMMETRIC SLOPE. A different tanh slope per side
    stops being asymmetric the moment both sides clip -- the curve becomes a
    square wave, which is purely ODD. So the tube character evaporated exactly
    where the knob was being pushed hardest, and the measured even content fell
    as the knob rose. A different rail HEIGHT survives any amount of drive.

    BLEND THE RECTIFIER BEFORE THE DRIVE, not after. Blending after meant the
    octave only broke through once it overwhelmed the saturator, which is a
    cliff rather than an arrival -- audible as "nothing, nothing, too much".
    """
    rect = 2.0*np.abs(x) - 1.0
    o = oct_max * d
    m = (1.0 - o)*x + o*rect
    g = (1.0 + 10.0*d) * m
    y = np.tanh(g)
    return dcblock(np.where(y >= 0, y, 0.62*y))

def wav(path, mono):
    st = np.repeat(np.clip(mono, -1, 1)[:, None], 2, axis=1)
    b = (st*32767).astype('<i2').tobytes()
    with open(path, 'wb') as f:
        f.write(b'RIFF'+struct.pack('<I', 36+len(b))+b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, 2, SR, SR*4, 4, 16)); f.write(b'data'+struct.pack('<I', len(b))+b)

SOURCES = [("bass", 36, dict(op2_coarse=2, op2_level=0.45)),
           ("keys", 48, dict(op2_coarse=4, op2_level=0.40))]
LEVELS  = [("a_15", 0.15), ("b_25", 0.25), ("c_35", 0.35), ("d_50", 0.50)]
DRIVES  = (0.2, 0.4, 0.6, 0.8, 1.0)

rows = []
for sname, note, kw in SOURCES:
    d0 = dry(note, **kw); pk = np.max(np.abs(d0)) + 1e-12
    wav(os.path.join(OUT, f"{sname}_0_dry.wav"), d0/pk*0.7)
    f0 = 440*2**((note-69)/12)
    for lname, omax in LEVELS:
        parts = []
        for drv in DRIVES:
            y = bite(d0/pk, drv, omax)
            y = y/(np.max(np.abs(y))+1e-12)*0.7
            parts.append(np.concatenate([y, np.zeros(int(0.25*SR))]))
            w = y[int(0.2*SR):int(0.2*SR)+SR//2]
            S = np.abs(np.fft.rfft(w*np.hanning(w.size))); fr = np.fft.rfftfreq(w.size, 1/SR)
            p = S*S
            odd = sum(p[np.abs(fr-k*f0) < 12].sum() for k in range(1, 40, 2))
            ev  = sum(p[np.abs(fr-k*f0) < 12].sum() for k in range(2, 40, 2))
            rows.append((sname, lname, drv, 10*np.log10(max(ev,1e-30)/max(odd,1e-30))))
        wav(os.path.join(OUT, f"{sname}_oct{lname}.wav"), np.concatenate(parts))

print("even/odd (dB) as BITE is turned up -- how fast the octave arrives\n")
print(f"  {'source':6s} {'octmax':7s} " + " ".join(f"{d:>7.1f}" for d in DRIVES))
for s in ("bass", "keys"):
    for lname, _ in LEVELS:
        v = [r[3] for r in rows if r[0] == s and r[1] == lname]
        print(f"  {s:6s} {lname:7s} " + " ".join(f"{x:7.1f}" for x in v))
print(f"\nfiles in {OUT} -- each plays BITE at 20/40/60/80/100%")
