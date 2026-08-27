# wall-bumper

A small standoff bumper that holds a storage bin off a wall, spacing it out
by a fixed gap while keeping a flat, support-free print orientation.

## Geometry

An I-beam shape when viewed from the top: two square contact flanges (one
against the bin, one against the wall) joined by a narrower connecting web.
All three sections share the same height/depth, so the part prints flat on
its widest face with no supports needed.

## Parameters

| Alias | Default | Meaning |
|---|---|---|
| `total_length` | 35.0 mm | Overall bumper length (bin face to wall face). Keep ≤ 38.1 mm (1.5 in). |
| `flange_width` | 10.0 mm | Contact face width (Y). |
| `flange_depth` | 10.0 mm | Contact face depth (Z) — a 1 cm square contact patch by default. |
| `flange_thickness` | 4.0 mm | X thickness of each flange. |
| `web_width` | 6.0 mm | Width (Y) of the narrowed connecting web, giving the I-beam profile. |

Derived: `web_length` (space between flanges), `web_y_offset` (centers the
web in Y), `flange2_x` (X position of the wall-side flange).

## Build

```
/cad-forward   # generated this script
/cad-build wall-bumper.py
```

Output: `/home/developer/cad-output/wall-bumper.FCStd`
