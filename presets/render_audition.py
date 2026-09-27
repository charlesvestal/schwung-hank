#!/usr/bin/env python3
"""Render the bank to WAVs to listen to: three notes per preset, held then released."""
import json, os, struct, subprocess, sys
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE)
import importlib.util as il, io, contextlib
sp=il.spec_from_file_location("genp",os.path.join(HERE,"gen_presets.py")); g=il.module_from_spec(sp)
_a=sys.argv[:]; sys.argv=["gen_presets.py"]
try:
    with contextlib.redirect_stdout(io.StringIO()): sp.loader.exec_module(g)
except SystemExit: pass
finally: sys.argv=_a
KEY={"op2_a":"op2_attack","op2_d":"op2_decay","op2_s":"op2_sustain","op2_r":"op2_release",
     "op1_a":"op1_attack","op1_d":"op1_decay","op1_s":"op1_sustain","op1_r":"op1_release",
     "res":"resonance","mix":"filter_mix","env_depth":"filter_env","f_a":"filter_attack",
     "f_d":"filter_decay","f_s":"filter_sustain","f_r":"filter_release","dist":"distortion"}
SR=44100; OUT=sys.argv[1]
bank=json.load(open(os.path.join(HERE,"bank.json"))); d=bank["_defaults"]
os.makedirs(OUT,exist_ok=True)
def wav(path,st):
    b=(np.clip(st,-1,1)*32767).astype('<i2').tobytes()
    with open(path,'wb') as f:
        f.write(b'RIFF'+struct.pack('<I',36+len(b))+b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH',16,1,2,SR,SR*4,4,16))
        f.write(b'data'+struct.pack('<I',len(b))+b)
for p in bank["presets"]:
    args=[f"{KEY.get(e,e)}={c(p.get(bk,d[bk]))}" for e,bk,c in g.FIELDS]
    parts=[]
    for note in (48,60,72):
        r=subprocess.run([os.path.join(ROOT,"build","hank_render"),
                          os.path.join(ROOT,"build","dsp_native.so"),
                          "2.2","1.4",str(note)]+args,capture_output=True,check=True)
        x=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
        parts.append(x[:len(x)//2*2].reshape(-1,2))
    wav(os.path.join(OUT,f"{p['cat']}_{p['name'].replace(' ','_')}.wav"),
        np.concatenate(parts))
print(f"{len(bank['presets'])} files in {OUT}  (each: C3, C4, C5 -- 1.4 s held, 0.8 s tail)")
