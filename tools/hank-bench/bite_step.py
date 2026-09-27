#!/usr/bin/env python3
"""Is there a step in the output as BITE crosses the point the shaper turns on?

Reported by a user as "a click on the Bite knob between 35 and 36". The shaper
is gated -- `dodist` flips the moment dist leaves zero -- so the question is
whether the curve is continuous with the dry signal at that boundary. If it is
not, the gate is a switch between two different waveforms and no amount of
parameter slewing can hide it: the slew moves `d`, and the jump is at d=0.

Two measurements, because they fail differently:
  LEVEL   the same note rendered either side of the boundary. A step here is
          what a listener hears as the knob passing a point.
  SAMPLE  the largest sample-to-sample jump while the knob is actually swept
          across it during a held note. This is the click itself.
"""
import os, subprocess, sys
import numpy as np
SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def render(bite, keys="48"):
    kw = dict(ratio=4, bright=0.45, bite=bite, tone=0.8, attack=0.0,
              decay=0.9, sustain=0.9, noise=0.0, voice_count=1, volume=1.0)
    r = subprocess.run([f"{ROOT}/build/hank_render", f"{ROOT}/build/dsp_native.so",
                        "1.5", "1.2", keys] + [f"{k}={v}" for k, v in kw.items()],
                       capture_output=True, check=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x[:len(x)//2*2].reshape(-1, 2).mean(axis=1)

print("BITE   peak dBFS   rms dBFS")
prev = None
worst = (0.0, None)
for b in [0.30, 0.33, 0.34, 0.345, 0.349, 0.351, 0.355, 0.36, 0.37, 0.40, 0.50]:
    w = render(b)[int(0.3*SR):int(1.0*SR)]
    pk = 20*np.log10(max(np.abs(w).max(), 1e-9))
    rms = 20*np.log10(max(np.sqrt((w*w).mean()), 1e-12))
    mark = ""
    if prev is not None:
        d = abs(rms - prev)
        if d > worst[0]: worst = (d, b)
        if d > 0.5: mark = f"   <-- {d:.2f} dB step"
    print(f" {b:.3f} {pk:9.2f} {rms:9.2f}{mark}")
    prev = rms

print(f"\nlargest adjacent step: {worst[0]:.2f} dB at BITE={worst[1]}")
if worst[0] > 0.5:
    print("FAIL: the shaper does not meet the dry signal where it switches on")
    sys.exit(1)
print("PASS: BITE crosses the shaper threshold without a level step")
