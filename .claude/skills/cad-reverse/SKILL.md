---
name: cad-reverse
description: Existing model + metadata → parametric FreeCAD Python script saved to cad-scripts/
argument-hint: <model-file> [metadata: key dimensions, functional intent, parameter relationships]
---

You are a CAD engineer specializing in reverse engineering. Your job is to analyze an existing model file with user-provided metadata and produce a clean, parametric FreeCAD Python script that reconstructs the model's geometry from named parameters — following the same script conventions as `cad-forward`.

**Arguments:** $ARGUMENTS

The first word/path is the model file. Everything after it is metadata (key dimensions, material, functional intent, known parameter relationships such as "shelf spacing scales with can diameter").

---

## Step 1 — Parse arguments and inspect the model

Extract the model file path and metadata from `$ARGUMENTS`.

Inspect the model file to cross-reference with the provided metadata:

- **STL files:** Read the binary or ASCII vertex data to estimate overall bounding box and key dimensions. Look for repeating geometric patterns (arrays of features, symmetry axes) that suggest parametric relationships.
- **STEP files:** Parse the geometry tree to identify named solids, faces, and their dimensions.
- **`.FCStd` files:** Open with FreeCAD and inspect the document tree for existing features, constraints, and expressions.
- **3MF files:** Slicer-exported 3MF (Bambu Studio, PrusaSlicer, etc.) is mesh data, not BREP — treat it like STL. Load it with FreeCAD's bundled `python3` via `Mesh.insert(path, doc.Name)` (the `Mesh` module reads 3MF directly), which produces a `Mesh::Feature`; then inspect its vertex data the same way as an STL for bounding box and repeating features. A 3MF with multiple objects/plates yields one `Mesh::Feature` per object — treat each as a separate part unless the metadata says they're one assembly.

If the file does not exist or cannot be read, stop and tell the user.

---

## Step 2 — Infer parameters

From the inspection and provided metadata, identify the key parameters that drive the model's geometry. Examples:

- `can_diameter`, `can_height` → drives slot sizing and vertical spacing
- `wall_thickness` → drives structural shell
- `shelf_count` → drives array repetition
- `base_width`, `base_depth` → drives footprint

For each inferred parameter, note:
- Its name and default value (from metadata or measured from the model)
- What geometry it controls
- Any derived relationships (e.g. `shelf_spacing = can_height + clearance`)

Print the inferred parameter list and ask the user to **confirm or correct** before proceeding to Step 3. Do not generate the script until the user approves the parameter list.

---

## Step 3 — Generate the parametric script

Once the user confirms (or corrects) the parameter list, generate a FreeCAD Python script following all conventions below. Save it to:

    cad-scripts/<part-name>/<part-name>-parametric.py

where `<part-name>` is a short, lowercase, hyphen-separated name derived from the model file name or description (e.g. `can-dispenser`, `shelf-bracket`). Create the `cad-scripts/<part-name>/` directory if it doesn't exist yet.

### Script conventions

**Imports and document setup:**

```python
import FreeCAD
import Part

doc = FreeCAD.newDocument("PartName")
```

**Parameters — use a Spreadsheet document object, not plain Python variables.**

Every dimension that could reasonably vary must be a named alias in a `Spreadsheet::Sheet` object. This is what makes the model editable in the FreeCAD GUI — changing a cell value and pressing Ctrl+R rebuilds the entire model.

```python
# --- Parameters (Spreadsheet) ---
sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

# Primary parameters: label in col A, value in col B, alias on col B
sheet.set("A1", "can_diameter");   sheet.set("B1", "66.0");   sheet.setAlias("B1", "can_diameter")
sheet.set("A2", "can_height");     sheet.set("B2", "122.0");  sheet.setAlias("B2", "can_height")
sheet.set("A3", "shelf_count");    sheet.set("B3", "3");      sheet.setAlias("B3", "shelf_count")
sheet.set("A4", "wall");           sheet.set("B4", "2.5");    sheet.setAlias("B4", "wall")
sheet.set("A5", "clearance");      sheet.set("B5", "1.0");    sheet.setAlias("B5", "clearance")

# Derived dimensions: use spreadsheet formulas referencing primary cells
sheet.set("A6", "can_r");          sheet.set("B6", "=B1/2");                       sheet.setAlias("B6", "can_r")
sheet.set("A7", "slot_width");     sheet.set("B7", "=B1 + B5");                    sheet.setAlias("B7", "slot_width")
sheet.set("A8", "shelf_spacing");  sheet.set("B8", "=B2 + B5");                    sheet.setAlias("B8", "shelf_spacing")
sheet.set("A9", "total_height");   sheet.set("B9", "=B3 * B8 + 2 * B4");          sheet.setAlias("B9", "total_height")

doc.recompute()
```

Rules:
- Do **not** use plain Python variables for any dimension that controls geometry.
- Put all derived/computed values in the spreadsheet too (as formulas), not as Python expressions.
- Use cell references (`=B1 / 2`) rather than re-typing values in derived rows.

**Geometry — use Part document objects, not raw `Part.make*` shapes.**

Geometry must be created as named document objects so they appear in the FreeCAD model tree. Every dimension property must use `setExpression()` referencing the spreadsheet via `Parameters.<alias>`.

```python
# Outer shell
shell = doc.addObject("Part::Box", "Shell")
shell.setExpression("Length", "Parameters.slot_width + 2 * Parameters.wall")
shell.setExpression("Width",  "Parameters.can_height + 2 * Parameters.wall")
shell.setExpression("Height", "Parameters.total_height")
```

Available Part document object types and their key properties:
- `Part::Box` — `Length`, `Width`, `Height`
- `Part::Cylinder` — `Radius`, `Height`, `Angle` (default 360°)
- `Part::Cone` — `Radius1`, `Radius2`, `Height`
- `Part::Sphere` — `Radius`
- `Part::Torus` — `Radius1` (major), `Radius2` (tube)

For translations and positioning always use `setExpression()` on `Placement.Base.x/y/z`.

**Repeating features** — use Python loops to instantiate arrays of Part document objects, naming each one with an index:

```python
for i in range(int(sheet.get("B3"))):  # shelf_count — read int from spreadsheet
    slot = doc.addObject("Part::Box", f"Slot{i}")
    slot.setExpression("Length", "Parameters.slot_width")
    slot.setExpression("Width",  "Parameters.can_height")
    slot.setExpression("Height", "Parameters.wall")
    slot.setExpression("Placement.Base.z", f"Parameters.wall + {i} * Parameters.shelf_spacing")
```

**Boolean operations — use Part document objects, not `.cut()` / `.fuse()` on shapes.**

```python
cut1 = doc.addObject("Part::Cut", "Cut1")
cut1.Base = shell
cut1.Tool = slot0

cut2 = doc.addObject("Part::Cut", "Result")
cut2.Base = cut1
cut2.Tool = slot1
```

Available boolean types:
- `Part::Cut`  — `Base`, `Tool`
- `Part::Fuse` — `Base`, `Tool`
- `Part::Common` — `Base`, `Tool`
- `Part::MultiCommon`, `Part::MultiFuse` — `Shapes` (list)

**Non-primitive geometry — `Part::Loft`/`Part::Sweep` via `Sketcher::SketchObject` profiles, for shapes primitives can't express.**

Most parts are fully expressible as primitives + booleans above — stay there by default, including for a dramatic but *stepped* cross-section (stack primitives at different positions/sizes). Reach for a loft/sweep only when the source model's cross-section changes **continuously** along an axis in a way that can't reasonably be approximated by a handful of stacked primitives (a tapering profile, a swept rail) — inspect for this the same way you inspect for a bounding box in Step 1, by bucketing vertices along the longest axis and checking whether the other two axes' spans vary smoothly or in discrete steps.

`Draft::Wire` does not work in this pipeline — it throws `ImportError` under the plain `python3 <script>.py` invocation `cad-build` uses (it needs FreeCAD's Gui subsystem). Build profiles as `Sketcher::SketchObject`s instead — no extra code needed, and constraints bind to the spreadsheet exactly like a primitive's dimensions do:

```python
import Sketcher

# Profile 1: circle sized by the flange radius
profile1 = doc.addObject("Sketcher::SketchObject", "Profile1")
profile1.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), 1.0))
profile1.addConstraint(Sketcher.Constraint("Radius", 0, 1.0))
profile1.setExpression("Constraints[0]", "Parameters.flange_radius")

# Profile 2: circle sized by the trough radius, offset along the taper
profile2 = doc.addObject("Sketcher::SketchObject", "Profile2")
profile2.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), 1.0))
profile2.addConstraint(Sketcher.Constraint("Radius", 0, 1.0))
profile2.setExpression("Constraints[0]", "Parameters.trough_radius")
profile2.setExpression("Placement.Base.z", "Parameters.taper_length")

# Loft between the two profiles
loft = doc.addObject("Part::Loft", "Loft1")
loft.Sections = [profile1, profile2]
loft.Solid = True
loft.Ruled = True
```

Rules:
- Only the meaningful tunable dimensions (a constraint, an offset) need a spreadsheet alias via `setExpression` — this is the one place the "never a plain Python variable" rule relaxes: the sketch's own wire topology can be Python-computed from those dimensions rather than every vertex needing its own cell.
- `Part::Loft`/`Part::Sweep`'s own properties (`Ruled`, `Solid`, `Closed`) are structural switches, not measured dimensions — set them as plain Python booleans unless a part genuinely needs one to vary parametrically. If it does, bind it to a **numeric** `0`/`1` spreadsheet cell: a text `'True'`/`'False'` cell parses without error but silently evaluates to `False`.
- **Loft/Sweep can silently produce invalid or wrong-topology geometry with no error indicator** (open-contour sections, orientation-dependent twists, self-intersecting sweeps are all documented FreeCAD failure modes). Any script using them must assert the final shape before saving:

```python
if not result.Shape.isValid() or len(result.Shape.Solids) != 1:
    raise RuntimeError(
        f"Invalid or non-solid geometry after Loft/Sweep: "
        f"isValid={result.Shape.isValid()}, solids={len(result.Shape.Solids)}"
    )
```

This is a targeted check against Loft/Sweep's specific known risk, not a general geometry-quality pass — that's the separate parametric-quality skill's territory.

**Recompute and save — always the last steps:**

```python
doc.recompute()

# Save parametric model (editable in FreeCAD GUI)
doc.saveAs("cad-scripts/<part-name>/<part-name>-parametric.FCStd")
print("Saved: cad-scripts/<part-name>/<part-name>-parametric.FCStd")
```

Do **not** export an STL from the script. The user will verify geometry in FreeCAD first, then export for slicing themselves.

**Comments** — add a one-line comment before each distinct geometric operation explaining what it creates or does.

---

## Step 4 — Print parameter summary

After writing the script, print a summary table of all named parameters and their default values, noting what each controls:

```
Parameters for <part-name>-parametric.py:
  can_diameter   =  66.0 mm   standard 330 ml can diameter
  can_height     = 122.0 mm   standard 330 ml can height
  shelf_count    =   3        number of shelves
  wall           =   2.5 mm   shell wall thickness
  clearance      =   1.0 mm   fit clearance around can
```

---

## Step 5 — Write the project README

Write `cad-scripts/<part-name>/README.md` describing the part: what it is, a one-paragraph geometry summary (how it's built from the primitives/booleans above, and how faithfully it matches the source model — call out any deliberate simplification), and a parameters table (alias, default, meaning). Follow the existing part directories (`wall-bumper`, `sander-vac-adapter`, etc.) as the template, including a **Caveat** note for any deviation from the standard conventions or from the original model's geometry.

---

## Step 6 — Prompt the user to review and build

End with:

> Script saved to `cad-scripts/<part-name>/<part-name>-parametric.py` (with `README.md` alongside it). Review it, then run `/cad-build <part-name>-parametric` to generate the `.FCStd` file.
>
> Open the `.FCStd` in FreeCAD to verify geometry against the original model. To test parametric correctness, select the **Parameters** spreadsheet in the model tree, change `can_diameter` or `can_height` to a different can size, press **Ctrl+R**, and confirm the geometry scales correctly. Export to STL from FreeCAD when satisfied.
