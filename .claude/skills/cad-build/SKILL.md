---
name: cad-build
description: Run a reviewed FreeCAD script inside the container and save the .FCStd model
argument-hint: <part-name>[-parametric] | <path/to/script.py>
---

You are a CAD build runner. Your job is to execute a reviewed FreeCAD Python script inside the container and report the result clearly.

**Script argument:** $ARGUMENTS

---

## Step 1 — Resolve the script path

If `$ARGUMENTS` contains a path separator (`/`), use it as-is — it's already a path relative to the repo root (or absolute).

Otherwise `$ARGUMENTS` is a bare `<part-name>` or `<part-name>-parametric`, naming a script that lives inside its own project directory. Strip a trailing `.py` if present, then resolve to:

    cad-scripts/<part-name>/<part-name>.py                  (cad-forward output)
    cad-scripts/<part-name>/<part-name>-parametric.py        (cad-reverse output, if the argument ends in "-parametric")

where `<part-name>` is the argument with any trailing `-parametric` removed.

If the file does not exist at the resolved path, stop and tell the user the full path you tried.

---

## Step 2 — Run the script

Execute the script with FreeCAD's bundled Python interpreter:

```bash
python3 <resolved-path>
```

Capture all stdout and stderr output.

---

## Step 3 — Report the result

**On success** (exit code 0):

- Print the full stdout from the script (it contains the `Saved:` line with the `.FCStd` path).
- Confirm success with the output file path, e.g.:

  > Build succeeded. Model saved to `cad-scripts/<part-name>/<part-name>.FCStd`.
  >
  > Open the `.FCStd` in FreeCAD to inspect the geometry. To adjust a parameter, select the **Parameters** spreadsheet in the model tree, edit the value, and press **Ctrl+R** to recompute.

**On failure** (non-zero exit code or Python traceback in output):

- Print the full error output verbatim so the user can read the traceback.
- Do **not** attempt to modify or fix the script.
- End with:

  > Build failed. Review the error above, fix `<script-path>`, and re-run `/cad-build <part-name>`.
