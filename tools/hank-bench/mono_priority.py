#!/usr/bin/env python3
"""Hold A, play B, release B -- the voice must return to A, still sounding.

It used to go silent: noteOff released whichever note the single voice was
playing without asking whether anything else was still held. Measured as
energy in the window after B is released, and as the pitch there.
"""
import os, subprocess, sys
import numpy as np
SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def render():
    r = subprocess.run([f"{ROOT}/build/mono_test", f"{ROOT}/build/dsp_native.so"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).mean(axis=1)

def pitch(w):
    S = np.abs(np.fft.rfft(w * np.hanning(w.size)))
    fr = np.fft.rfftfreq(w.size, 1 / SR)
    S[fr < 40] = 0
    return float(fr[int(S.argmax())])

m = render()
# timeline written by mono_test: A at 0.0, B at 0.5, B off at 1.0, A off at 1.5
a  = m[int(0.20*SR):int(0.45*SR)]
b  = m[int(0.70*SR):int(0.95*SR)]
ret= m[int(1.20*SR):int(1.45*SR)]
db = lambda w: 20*np.log10(max(float(np.sqrt((w*w).mean())), 1e-12))
print(f"  A held      {db(a):7.1f} dBFS  {pitch(a):6.1f} Hz")
print(f"  B on top    {db(b):7.1f} dBFS  {pitch(b):6.1f} Hz")
print(f"  B released  {db(ret):7.1f} dBFS  {pitch(ret):6.1f} Hz")
bad = []
if db(ret) < db(a) - 12: bad.append("the voice went quiet instead of returning to A")
if abs(pitch(ret) - pitch(a)) > pitch(a)*0.06: bad.append("it did not return to A's pitch")
if bad:
    for x in bad: print("  FAIL:", x)
    sys.exit(1)
print("  PASS: mono returns to the held note, at its pitch, still sounding")
