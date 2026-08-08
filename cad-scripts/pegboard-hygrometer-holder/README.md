# pegboard-hygrometer-holder

A pegboard-mountable cradle that holds a small hygrometer, open at the
front for reading the display, with ventilation slots so airflow reaches
the sensor.

## Geometry

A four-walled box shell (outer box minus an interior pocket, open on the
front face) with two cylindrical pegs on the back for standard pegboard
hole spacing, a ventilation slot cut through each side of the back wall,
and two diagonal ribs across the back face for stiffness.

**Caveat:** the ribs' angle and length are computed with Python `math` at
script-generation time from constants that mirror `hygrometer_width`,
`hygrometer_height`, `wall_thickness`, and `tolerance` (see the `_hw, _hh,
_wt, _tol` block). They are **not** wired to the spreadsheet via
`setExpression`. Changing those spreadsheet cells in the FreeCAD GUI and
pressing Ctrl+R will resize the cradle but leave the ribs in their old
position/angle — regenerate the script instead if those dimensions change.

## Parameters

| Alias | Default | Meaning |
|---|---|---|
| `hygrometer_width` | 47.0 mm | Width of the hygrometer body. |
| `hygrometer_height` | 25.0 mm | Height of the hygrometer body. |
| `hygrometer_depth` | 14.5 mm | Depth of the hygrometer body. |
| `peg_spacing` | 25.0 mm | Distance between the two pegboard pegs. |
| `peg_hole_diameter` | 4.5 mm | Pegboard hole diameter the pegs must fit. |
| `peg_hook_depth` | 8.0 mm | How far each peg protrudes from the back. |
| `wall_thickness` | 2.0 mm | Shell wall thickness around the pocket. |
| `tolerance` | 0.2 mm | Fit clearance around the hygrometer body. |
| `vent_width` | 8.0 mm | Width of each ventilation slot. |
| `rib_width` | 3.0 mm | Width of each diagonal back rib. |
| `rib_thickness` | 1.5 mm | Thickness (protrusion) of each rib. |

Derived: `outer_width`/`outer_height`/`outer_depth`, `pocket_width`/
`pocket_height`, `peg_radius`, peg/vent placement coordinates, and
`rib_length` (diagonal of the interior pocket).

## Build

```
/cad-build pegboard-hygrometer-holder.py
```

Output: `/home/developer/cad-output/pegboard-hygrometer-holder.FCStd`
