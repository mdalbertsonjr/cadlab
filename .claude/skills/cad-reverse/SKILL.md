---
name: cad-reverse
description: Existing model + metadata → parametric FreeCAD Python script saved to cad-output/
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

    /home/developer/cad-output/<part-name>-parametric.py

where `<part-name>` is a short, lowercase, hyphen-separated name derived from the model file name or description (e.g. `can-dispenser`, `shelf-bracket`).

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

**Recompute and save — always the last steps:**

```python
doc.recompute()

# Save parametric model (editable in FreeCAD GUI)
doc.saveAs("/home/developer/cad-output/<part-name>-parametric.FCStd")
print("Saved: /home/developer/cad-output/<part-name>-parametric.FCStd")
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

## Step 5 — Prompt the user to review and build

End with:

> Script saved to `/home/developer/cad-output/<part-name>-parametric.py`. Review it, then run `/cad-build <part-name>-parametric.py` to generate the `.FCStd` file.
>
> Open the `.FCStd` in FreeCAD to verify geometry against the original model. To test parametric correctness, select the **Parameters** spreadsheet in the model tree, change `can_diameter` or `can_height` to a different can size, press **Ctrl+R**, and confirm the geometry scales correctly. Export to STL from FreeCAD when satisfied.
