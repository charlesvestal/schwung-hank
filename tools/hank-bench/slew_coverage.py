#!/usr/bin/env python3
"""Every Params float must be slewed or explicitly declared structural.

sp_ is what the voices render from. A field in neither slewParams nor the
"structural, never slewed" block reaches sp_ only through `sp_ = p_`, which
runs when no voice is sounding -- so the control works from silence and is
dead while anything is ringing. That is invisible to every bench measurement
here, because each rendered note starts from an idle engine, and it presents
to a player as "this knob does nothing". It shipped that way for `noise`.
"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
hdr = open(os.path.join(ROOT, "src", "dsp", "hank_engine.h")).read()
cpp = open(os.path.join(ROOT, "src", "dsp", "hank_engine.cpp")).read()

body = hdr[hdr.index("struct Params {"):]
body = body[:body.index("\n};")]
fields = []
for line in body.split("\n"):
    line = re.sub(r"/\*.*?\*/", "", line).split("//")[0].strip()
    m = re.match(r"^float\s+(.*);$", line)
    if not m: continue
    for decl in m.group(1).split(","):
        name = decl.strip().split("=")[0].strip()
        if name: fields.append(name)

slew = cpp[cpp.index("void Engine::slewParams("):]
slew = slew[:slew.index("\n}")]
struct = cpp[cpp.index("/* Structural, never slewed"):]
struct = struct[:struct.index("/* crushLevels")]
covered = set(re.findall(r"\bd\.(\w+)", slew)) | set(re.findall(r"\bsp_\.(\w+)", struct))

missing = [f for f in fields if f not in covered]
print(f"{len(fields)} Params floats, {len(covered)} covered")
if missing:
    print("  NOT SLEWED AND NOT DECLARED STRUCTURAL:", ", ".join(missing))
    print("  (works from silence, inert while a note rings)")
    sys.exit(1)
print("  every Params float is slewed or structural")
