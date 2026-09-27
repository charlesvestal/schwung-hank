#!/usr/bin/env python3
"""Emit src/module.json from ONE param table.

chain_params (metadata for the chain UI) and ui_hierarchy (what the knob grid
lists, and in what order) describe the same 34 parameters. Writing them out
twice by hand is how they drift, so both come from PARAMS below.

Page layout: the planner chunks a level's `knobs` array at EXACTLY 8 per page
(page_plan.mjs, `chunk(authoredKeys, perPage)`), so the groups below are sized
to 8 deliberately -- each envelope's four keys stay contiguous and start a row,
which is what keeps the ADSR graphic inside one row after alignGroupsToRows.
"""
import json, os, collections

def P(key, name, short, typ="float", lo=0.0, hi=1.0, step=0.01, default=0.0,
      unit=None, options=None, viz=None, live=False):
    d = {"key": key, "name": name, "short_name": short, "type": typ,
         "min": lo, "max": hi, "step": step, "default": default}
    if unit:    d["unit"] = unit
    if options: d["options"] = options
    if viz:     d["viz"] = viz
    if live:    d["live"] = True
    return d

ONOFF = ["Off", "On"]
# Must equal curves::RATIO_TABLE in src/dsp/hank_curves.h, in order.
RATIO_LABELS = ["0.5", "1", "1.5", "2", "2.5", "3", "3.7", "4", "5", "5.4", "6", "7", "8", "9.2", "11", "14"]

# RATIO_LABELS and curves::RATIO_TABLE are ONE fact written in two files, and a
# drift between them is a knob that reads 3.7 and sounds like 4 -- silent, and
# invisible to every audio measurement, because both halves are individually
# self-consistent. Checked here so build.sh fails rather than the device.
def _check_ratio_table():
    import re, os
    h = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "src", "dsp", "hank_curves.h")
    src = open(h).read()
    blk = src[src.index("RATIO_TABLE[] = {"):]
    blk = blk[:blk.index("}")]
    tbl = [float(x) for x in re.findall(r"([0-9.]+)f", blk)]
    lbl = [float(x) for x in RATIO_LABELS]
    assert tbl == lbl, f"RATIO_LABELS {lbl} != curves::RATIO_TABLE {tbl}"
_check_ratio_table()

PARAMS = [
    # ---- page 1: THE EIGHT. This is the instrument.
    # The wave viz spans RATIO/BRIGHT/BITE, which are exactly the three knobs
    # that shape the modulator: RATIO sets the cycles, BRIGHT the swing, BITE
    # the deformation. Every key stays an independent knob; the graphic is
    # drawn across them.
    # AN ENUM OF THE ACTUAL RATIOS, not a 0..1 position along a hidden table.
    # As a float the cell and the screen reader both said "0.28" for a ratio of
    # 2.5 -- meaningless, on the one knob whose value is a nameable musical
    # fact. The labels ARE curves::RATIO_TABLE; the two must not drift.
    P("ratio","Ratio","Ratio","int",0,15,1,4,options=RATIO_LABELS,
      viz={"group":"fm","role":"ratio","kind":"custom:hank_wave"}),
    P("bright","Bright","Bright","float",0.0,1.0,0.01,0.35,unit="%",
      viz={"group":"fm","role":"level"}),
    P("bite","Bite","Bite","float",0.0,1.0,0.01,0.0,unit="%",
      viz={"group":"fm","role":"feedback"}),
    P("tone","Tone","Tone","float",0.0,1.0,0.01,0.8,unit="%"),
    P("attack","Attack","Atk","float",0.0,1.0,0.01,0.0,unit="%"),
    P("decay","Decay","Dec","float",0.0,1.0,0.01,0.45,unit="%"),
    P("sustain","Sustain","Sus","float",0.0,1.0,0.01,0.7,unit="%"),
    P("noise","Noise","Nois","float",0.0,1.0,0.01,0.0,unit="%"),

    # ---- page 2: the machine. Housekeeping only -- nothing that makes a sound.
    #
    # WHAT WAS HERE AND IS NOT ANY MORE, AND WHY:
    #
    #   macro_mode   The Manual pages are gone (below), so this switched to
    #                nothing. A mode control with one mode is furniture.
    #   crush        The only sound-shaping control stranded on a housekeeping
    #                page, which is precisely how it read. It survived from the
    #                original param set rather than being chosen, no preset used
    #                it, and bit reduction is available as a chain effect where
    #                it can be shared by everything in the slot.
    #   keytrack     It tracks the FILTER -- the one TONE drives, which is very
    #                much still here -- so the name was doing the confusing, not
    #                the feature. It is a set-and-forget that nothing wants off,
    #                and it is now always on at half tracking (see cutoffHz).
    #   p_env/p_decay The pitch envelope went with the PITCH macro.
    P("voice_count","Voices","Voc","int",1,16,1,8),
    P("glide","Glide","Gld","float",0.0,1.0,0.01,0.0,unit="%"),
    P("pitch","Transpose","Trans","float",-96.0,96.0,1.0,0.0,unit="st"),
    P("volume","Volume","Vol","float",0.0,1.0,0.01,1.0,unit="%"),

    # THE MANUAL PAGES ARE GONE, not hidden.
    #
    # They were three pages of raw engine values that applyMacros overwrote on
    # every block, so with Macros on they responded to being turned and changed
    # no sound. Gating them on macro_mode fixed the lie but kept the mode, and a
    # mode nobody switches is a page nobody finds plus a switch everybody
    # wonders about. The engine still has every one of these fields; the macros
    # are simply the only thing that writes them, which is what an eight-knob
    # instrument means.
]

PRESET = {"key":"preset","name":"Preset","short_name":"Preset","type":"int",
          "min":0,"max_param":"preset_count","default":0}

KNOBS = [p["key"] for p in PARAMS] + ["preset"]
# 32 macros+machine, plus the preset knob the generator appends. The count is
# asserted so a param added to PARAMS and forgotten on a LEVEL is a build error
# rather than a control that exists and cannot be reached.
assert len(KNOBS) == 13, len(KNOBS)

# ONE LEVEL PER PAGE, AND THE FIRST ONE IS A PERFORMANCE PAGE.
#
# Two things drive this layout.
#
# 1. THE HEADER IS WHAT TELLS THREE ADSR ROWS APART. Hank has three envelopes
#    -- OP2's (timbre), OP1's (amplitude) and the filter's -- and they draw the
#    same graphic under the same four labels. On one level the headers read
#    "Main", "Main - 2", "Main - 3", so nothing says WHICH you are editing.
#    A named level per page puts that in the header, and each envelope lands on
#    a page named for it.
#
# 2. THE LANDING PAGE SHOULD BE THE ONE YOU PLAY FROM. Ordering everything by
#    declaration made page one "OP2's eight parameters" by accident. Main is
#    where you arrive every single time, so it holds what you actually reach
#    for. This is the page the CHAIN EDITOR shows while a slot is playing.
#
#    CUTOFF AND RESONANCE ARE KNOBS 1 AND 2 -- the first two your hand finds --
#    with the rest of the filter macro set beside them and the FM timbre
#    controls on the row below. What is NOT here is filter_on and keytrack:
#    those are set once when you build the patch, not reached for while you
#    play, and a cockpit should not spend its best two slots on a bypass
#    switch. They live on the Filter page. The four that are here appear on the
#    Filter page too -- deliberate duplication, the way a macro page works.
#
# The landing page is called "Main" whatever we name its level (page_plan.mjs
# fixes that: "one consistent name for where you land"), so it declares a
# `subtitle` to say which page it is.
#
# CONSISTENT POSITIONS MATTER ON THE DETAIL PAGES, NOT ON MAIN. Each detail
# page leads with its own graphic in row 1 -- envelope, envelope, filter curve,
# envelope -- so paging through them the picture is always in the same place.
#
# Main is exempt on purpose: it is a cockpit, not a clone of the pages behind
# it. It is laid out for reach -- the wave over the four timbre controls, the
# filter curve over the four filter controls -- and the Filter page is NOT
# rearranged to agree with it. (It was, briefly, and that made the Filter page
# worse to serve a rule that bought nothing.)
BY = {p["key"]: p for p in PARAMS + [PRESET]}
LEVELS = [
    ("main", "Main", None, [
        "ratio", "bright", "bite", "tone",
        "attack", "decay", "sustain", "noise"]),
    ("setup", "Setup", None, [
        "voice_count", "glide", "pitch", "volume", "preset"]),
]
_seen = set()
for _k, _n, _s, _ks in LEVELS:
    for _x in _ks:
        assert _x in BY, f"unknown key {_x}"
        _seen.add(_x)
assert _seen == set(KNOBS), f"unplaced: {set(KNOBS) - _seen}"

mod = {
    "id": "hank",
    "name": "Hank",
    "abbrev": "HK",
    "version": "0.6.0",
    "description": ("Two-operator FM on eight knobs, one page: ratio, brightness, bite, "
                    "one envelope pair, noise and a tone sweep. 32 presets."),
    "author": "charlesvestal",
    "license": "MIT",
    "component_type": "sound_generator",
    "api_version": 2,
    # 1.2.0 is where ensureComponentWidgets and canvas_script first shipped, so it
    # is the oldest host that can draw the wave across ratio/bright/bite. An
    # older one loads the module and silently draws dials instead.
    "min_host_version": "1.2.0",
    "ui": "ui.js",
    "dsp": "dsp.so",
    "capabilities": {
        "audio_out": True,
        "audio_in": False,
        "midi_in": True,
        "midi_out": False,
        "aftertouch": False,
        "chainable": True,
        "pad_layout": "chromatic",
        # Without this the custom widget is never registered and the waveform
        # falls through to a plain dial -- correct page, no error, no log line.
        "canvas_script": "canvas.js",
        "chain_params": PARAMS + [PRESET],
    },
    "ui_hierarchy": {
        "levels": {
            key: dict({"name": name,
                       "knobs": ks,
                       "params": [BY[k] for k in ks]},
                      **({"subtitle": sub} if sub else {}),
                      **({"list_param": "preset", "count_param": "preset_count",
                          "name_param": "preset_name"} if key == LEVELS[0][0] else {}),
)
            for key, name, sub, ks in LEVELS
        }
    },
}
here=os.path.dirname(os.path.abspath(__file__))
dst=os.path.join(here,"..","src","module.json")
open(dst,"w").write(json.dumps(mod,indent=2)+"\n")
# THE CONTRACT MUST ALSO BE SERVABLE FROM get_param.
#
# module.json alone is not enough: the shadow UI asks the COMPONENT for
# `ui_hierarchy` and `chain_params` over the param channel, and a module that
# does not answer gets no knob grid at all -- just the preset row. Emitting both
# from this same table means the file and the wire can never disagree.
contract = os.path.join(here, "..", "src", "dsp", "hank_contract.h")
hier = json.dumps(dict(mod["ui_hierarchy"], modes=None), separators=(",", ":"))
cp   = json.dumps(mod["capabilities"]["chain_params"], separators=(",", ":"))
for name, blob in (("ui_hierarchy", hier), ("chain_params", cp)):
    assert ')JSON"' not in blob, name
open(contract, "w").write(
    "/* GENERATED by tools/gen_module_json.py -- do not edit. */\n"
    "#ifndef HANK_CONTRACT_H\n#define HANK_CONTRACT_H\n\n"
    "/* Served from get_param(): the shadow UI asks the component for these,\n"
    " * and a module that answers neither shows no knob grid. */\n"
    "static const char HANK_UI_HIERARCHY[] = R\"JSON(" + hier + ")JSON\";\n\n"
    "static const char HANK_CHAIN_PARAMS[] = R\"JSON(" + cp + ")JSON\";\n\n"
    "#endif\n")
print(f"wrote {contract}: ui_hierarchy {len(hier)} B, chain_params {len(cp)} B")

print(f"wrote {dst}: {len(PARAMS)} params + preset, {len(KNOBS)} knobs")
for key, name, sub, ks in LEVELS:
    label = f"{name} - {sub}" if sub else name
    print(f"   {label:<16} ({key}): {len(ks)} keys")
