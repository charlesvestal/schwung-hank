# Hank

A 2-operator FM synthesizer for [Schwung](https://github.com/charlesvestal/schwung)
on Ableton Move.

> **hank** — a loop of continuous yarn, usually twisted. Yarn in hank form must
> be wound into a ball before you can use it.

Eight knobs on one page are the whole instrument. There is no manual mode and
no page of raw operator values: the eight macros drive the engine, and anything
they do not reach is chosen for you so that it cannot be set wrong.

## The eight

A macro is not a relabelled parameter — most of these drive several engine
values at once, on purpose, so that combinations which only ever sound wrong
cannot be reached.

| Knob | What you hear | What it actually drives |
|---|---|---|
| **Ratio** | Whole numbers are harmonic tones; the rest are bells and metal. | Modulator frequency, declared as an **enum of the 16 ratios themselves** — the cell and the screen reader say `2.5`, not a position along a hidden table. Stepped rather than continuous so a turn always lands on something usable. |
| **Bright** | The main timbre control: sine at the bottom, brassy in the middle, ragged at the top. | The FM index, 0 to 14 radians, squared so the low end gets most of the travel. Its **last third also tops up feedback by 25%**, so a very bright patch has teeth before you touch Bite. |
| **Bite** | Two kinds of dirt from one knob. | **0 → 0.6: modulator self-feedback** (0 to 0.75) — the operator feeds its own output back into its phase, so the *source* gets richer. **0.35 → 1.0: the shaper** — tube-style asymmetry throughout with an octave blended in as you push, then a soft rail. The first half changes the source, the second changes what is done to it, and they overlap. |
| **Tone** | Dark to open, with a resonant bump around the middle. | Filter cutoff, 600 Hz to 18 kHz, at half keytracking. Resonance is *derived*, peaking at Tone ≈ 0.55 and falling away at both ends, so it is a tone control rather than a filter panel. |
| **Attack** | Immediate to a slow swell. | Both operators. 0.5 ms to 600 ms; the modulator opens 30% sooner. |
| **Decay** | A click to an eight-second tail. Also the release. | Both operators, 1.5 ms to 1.2 s of time constant. **The modulator is always 2.2x shorter than the carrier** — see below. |
| **Sustain** | How much of the note, and of its timbre, holds. | Carrier sustain 0 to 1; modulator sustain **0.30 + 0.55 x**, so timbre fades but never disappears. |
| **Noise** | A chiff on the attack, or a hat if you hold it. | White noise crossfaded into the carrier ahead of the filter, on the *modulator* envelope — so it is a transient by default and opens out as Sustain rises. The carrier ducks by the same law, so the knob crossfades rather than stacking. |

Ratio, Bright and Bite are drawn as one live waveform showing what the
modulator is doing.

Setup holds Voices, Glide, Transpose, Volume and the preset list. Volume is a
plain multiplier — full is unity, and it only attenuates.

## Signal path

```
OP2 (ratio, self-feedback, envelope)
  -> phase-modulates ->
OP1 (carrier at the played pitch, envelope)
  + noise on the modulator envelope
  -> morphing state-variable filter
  -> voice out

sum of voices -> bite shaper -> volume -> soft knee
```

Phase modulation rather than true frequency modulation, as every classic "FM"
synth does — it is what lets an operator feed back on itself without drifting
in pitch.

Two couplings are deliberate and not exposed:

- **The modulator envelope is 2.2x shorter than the carrier's, at every
  setting.** Held as a ratio in *time*, not in knob position — scaling the
  position of an exponential control fixes the exponent instead, which made the
  ratio drift from 1.6x to 11x with note length and sorted every patch into
  growls or bells.
- **It never closes completely.** Tying the modulator's sustain to the
  amplitude's meant a percussive patch decayed to a bare sine within a few tens
  of milliseconds, so Ratio stopped mattering. A floor keeps a steady-state
  timbre while still fading brightness before loudness.

At one voice the synth is mono with glide between overlapping notes, and
releasing the top note returns to the one still held without retriggering.

## Presets

32 across bass, keys, bells, leads, pads, percussion and effects.

Levels are matched on a **five-note chord**, not on a single note, so chords
have headroom rather than single notes being as loud as possible. Preset
loudness is carried by a hidden `preset_gain`, leaving the Volume knob meaning
the same thing on every patch.

## Building

```bash
./scripts/build.sh     # cross-compiles for ARM64 in Docker
./scripts/install.sh   # deploys to ableton@move.local
```

`src/module.json`, `src/dsp/hank_contract.h` and `src/dsp/hank_presets.h` are
**generated** — from `tools/gen_module_json.py` and `presets/bank.json`.
`build.sh` regenerates them, so edit the generators, not the outputs.

## The bench

`tools/hank-bench/` builds the DSP natively and measures it. The curves in
`src/dsp/hank_curves.h` are fitted to those measurements rather than guessed.

| Tool | Asks |
|---|---|
| `macro_sweep.py` | Does each macro behave like a musical control across its whole travel — no silence, no jumps, level held? Two windows, because a single late window cannot see an attack-shaped control. |
| `bank_spread.py` | Is the factory bank a range of sounds, or one sound 32 times? Nearest-neighbour distance in a five-feature space. |
| `bite_step.py` | Does BITE cross the point the shaper switches on without a step? The curve has to meet the dry signal at zero, or the gate is a switch between two waveforms and no slew can hide it. |
| `note_lifecycle` | Does a note stop when released, and when the preset changes, without a click? |
| `mono_priority.py` | Does a mono voice return to the note still held? |
| `slew_coverage.py` | Is every `Params` float slewed or explicitly structural? One that is neither works from silence and is dead while a note rings. |
| `host_test` | Every preset loads, sounds, and lands in range. |

## Licence

MIT.
