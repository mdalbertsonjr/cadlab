# can-dispenser-ramp

The sloped channel piece of a 5-part gravity-fed can dispenser (the other
parts — `Lid`, `Open End`, `Tongue`, `Turnover End` — aren't reconstructed
yet). Cans lie on their side and roll/slide down this trough to dispense.
Reverse-engineered from a slicer-exported `.3mf` reference model at
`~/Documents/3D-Printing/Models/Can Dispenser 12oz - Ramp.3mf` via
`/cad-reverse`, sized for a standard 12oz (355 mL) can.

## Geometry

An outer block (`ramp_length` × `channel_width` × `side_wall_height`) with a
full-depth open slot cut through it lengthwise (`trough_width` wide, leaving
`wall` thickness on each side). For most of the length (`main_length`) that
slot is a constant-cross-section box cut — geometric inspection of the
source mesh found the real part's cross-section is genuinely constant there,
so a primitive is both sufficient and correct, not a simplification.

Over the last `taper_length` of the part, the slot **continuously narrows to
nothing** — the two side rails close up flush, guiding the can out through a
controlled opening rather than dropping straight through. That's a real
continuous profile change primitives can't express, so it's cut with a
`Part::Loft` from the slot's open rectangular profile (a `Sketcher::SketchObject`
sized by `trough_width`/`side_wall_height`) down to a single point
(`Part::Vertex`) at the far end, per the loft/sweep convention added in
`.claude/skills/cad-reverse/SKILL.md`.

**Caveat:** this still doesn't chase the source mesh's exact surface —
rounded corners/fillets and any fine detail within the taper aren't modeled,
just its overall closing profile (rectangle → point). `main_length` and
`taper_length` split the measured `ramp_length` at the point cross-sectioning
found the floor start rising; both are independent measured constants, not
derived from the can dimensions.

## Parameters

| Alias | Default | Meaning |
|---|---|---|
| `can_diameter` | 66.0 mm | Standard 12oz can diameter (given). |
| `can_height` | 122.7 mm | Standard 12oz can height (given). |
| `wall` | 3.5 mm | Channel wall thickness (measured). |
| `clearance` | 13.0 mm | Extra room added around the can so it can roll freely (measured). |
| `side_wall_height` | 85.5 mm | Height of the channel's side walls (independent, measured). |
| `main_length` | 171.6 mm | Length of the constant-cross-section span (independent, measured). |
| `taper_length` | 61.3 mm | Length over which the slot closes to nothing (independent, measured). |
| `channel_width` *(derived)* | `= can_height + 2*wall + clearance` ≈ 142.7 mm | Y width of the block/slot — scales with `can_height`. |
| `trough_width` *(derived)* | `= channel_width - 2*wall` ≈ 135.7 mm | Width of the open slot, inset by the wall on each side. |
| `ramp_length` *(derived)* | `= main_length + taper_length` ≈ 232.9 mm | Overall part length. |

## Validation

Headless recompute test (swapping in an 8.4oz slim can, 53.0×131.0mm):
`channel_width` grew to 151.0mm and `trough_width` to 144.0mm exactly as the
formulas predict, `main_length`/`taper_length`/`side_wall_height` stayed
fixed, and the result stayed a single valid solid — confirms the parametric
relationships (and the loft) hold under Ctrl+R, not just at the default
values.

**Sketch-profile pitfall hit and fixed while building this:** an
under-constrained (or mis-indexed `Horizontal`/`Vertical`) profile sketch can
produce a shape that looks completely normal on casual inspection but is
silently null under `.isValid()`'s deep check — not caught until the
validity assert runs. Documented as a convention rule in
`.claude/skills/cad-reverse/SKILL.md`.

## Build

```
/cad-build can-dispenser-ramp-parametric
```

Output: `cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.FCStd`
