#!/usr/bin/env python3
"""Is the factory bank actually a range of sounds, or one sound 32 times?

"A lot of our presets sound the same" is a measurable claim, and it is not
measurable from the preset VALUES -- two settings can differ on paper and land
in the same place, which is exactly what a mis-scaled control does. So render
every preset and describe it by what a listener discriminates on: where the
energy sits, how long the note lasts, how fast it arrives, and how noisy it is.

Reported as nearest-neighbour distance in that space. A bank with a small
worst-case nearest neighbour is a bank of duplicates however different its
numbers look.
"""
import json, os, subprocess, sys
import numpy as np
SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
bank = json.load(open(os.path.join(ROOT, "presets", "bank.json")))
d = bank["_defaults"]

def render(p):
    kw = {k: p.get(k, d[k]) for k in
          ("ratio","bright","bite","tone","attack","decay","sustain","noise")}
    # HONOUR THE PRESET'S OWN VOLUME. Pinning it to 0.5 made per-preset level
    # trimming invisible to every measurement taken here -- the bank was
    # normalised and the harness reported the same 12.4 dB spread as before,
    # because it was rendering a bank nobody ships.
    kw.update(macro_mode=1, voice_count=1,
              volume=p.get("volume", d["volume"]) / 100.0)
    r = subprocess.run([f"{ROOT}/build/hank_render", f"{ROOT}/build/dsp_native.so",
                        "2.5", "2.0", "48"] + [f"{k}={v}" for k, v in kw.items()],
                       capture_output=True, check=True)
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x[:len(x)//2*2].reshape(-1, 2).mean(axis=1)

def feats(m):
    env = np.abs(m)
    n = max(1, int(0.005*SR))
    env = np.convolve(env, np.ones(n)/n, mode="same")
    pk = env.max() + 1e-12
    ipk = int(env.argmax())
    # time to reach 90% of peak, and time to fall 20 dB after it
    atk = float(np.argmax(env >= 0.9*pk)) / SR
    tail = env[ipk:]
    below = np.where(tail < pk*0.1)[0]
    dec = float(below[0])/SR if below.size else float(tail.size)/SR
    w = m[:int(0.4*SR)]
    S = np.abs(np.fft.rfft(w*np.hanning(w.size))); fr = np.fft.rfftfreq(w.size, 1/SR)
    p = S*S; p[fr < 20] = 0
    cen = float((fr*p).sum()/(p.sum()+1e-30))
    hf  = float(S[fr > 3000].sum()/(S.sum()+1e-30))
    # spectral flatness: a sine is peaky, noise is flat -- separates hats from bells
    q = p[fr > 100] + 1e-20
    flat = float(np.exp(np.log(q).mean()) / q.mean())
    return np.array([np.log2(max(cen, 20)), np.log2(max(atk, 1e-4)),
                     np.log2(max(dec, 1e-3)), hf*6.0, flat*6.0])

ps = bank["presets"]
F = np.array([feats(render(p)) for p in ps])
F = (F - F.mean(axis=0)) / (F.std(axis=0) + 1e-9)
D = np.sqrt(((F[:, None, :] - F[None, :, :])**2).sum(-1))
np.fill_diagonal(D, np.inf)
nn = D.min(axis=1)
order = np.argsort(nn)
print(f"{len(ps)} presets; nearest-neighbour distance in a 5-feature space")
print(f"  worst {nn.min():.2f}   median {np.median(nn):.2f}   mean {nn.mean():.2f}\n")
print("  closest pairs (candidates for 'these two sound the same'):")
seen = set()
for i in order:
    j = int(D[i].argmin())
    key = tuple(sorted((int(i), j)))
    if key in seen: continue
    seen.add(key)
    print(f"    {nn[i]:5.2f}  {ps[i]['name']:<12s} <-> {ps[j]['name']}")
    if len(seen) >= 6: break
bad = [ps[i]["name"] for i in range(len(ps)) if nn[i] < 0.5]
print("\n  TOO CLOSE (<0.50):", ", ".join(bad) if bad else "none")
sys.exit(1 if bad else 0)
