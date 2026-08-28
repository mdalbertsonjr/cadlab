# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, OpenCode, etc.)
when working in this repository.

## What this repo is

A monorepo for CAD projects: parametric FreeCAD part scripts, the design
knowledge behind them, and the containerized agent tooling used to generate
and build them. There is no traditional build/test/lint pipeline — this is a
scripts-and-agent-workflow repo, not an application.

## Architecture: the CAD generation pipeline

The core workflow is a four-stage agent pipeline defined as skills under
`.claude/skills/<skill-name>/SKILL.md`. This path is a Claude Code Agent
Skill location, but OpenCode discovers skills there too (as a
"Claude-compatible" search path), so one copy serves both agents — do not
duplicate these under `.opencode/` or `.agents/`.

1. **`cad-forward`** — natural language part description → a new parametric
   FreeCAD Python script written straight to
   `cad-scripts/<part-name>/<part-name>.py`, plus a `README.md` alongside it.
2. **`cad-reverse`** — an existing model file (STL/STEP/FCStd/3MF) + user-supplied
   metadata → a reconstructed parametric script, same output convention as
   `cad-forward` but suffixed `-parametric.py`. Requires the agent to print
   inferred parameters and get user confirmation before generating code.
3. **`cad-build`** — executes a reviewed script with FreeCAD's bundled
   `python3` and reports the resulting `.FCStd` path, or the raw traceback on
   failure. It never edits scripts itself — fixing a failed build is a
   `cad-forward`/`cad-reverse` follow-up, not a `cad-build` job.
4. **`cad-slice`** — slices a built part and its original reference model
   through the same headless PrusaSlicer with the same checked-in profile and
   compares the two G-codes (aggregate metrics, then per-layer toolpaths) —
   the machine check on geometric fidelity that runs before any human time is
   spent on GUI review or printing. Same discipline as `cad-build`: it never
   edits scripts; a FAIL feeds the next `cad-forward`/`cad-reverse` iteration.

Each generated part lives in its own directory under `cad-scripts/`
(`cad-scripts/<part-name>/<part-name>.py` plus a `README.md` describing the
part, its parameters, and any deviation from the standard conventions). The
`.FCStd` a build produces lands in that same directory but is never
committed — it's a local, regeneratable artifact (see `.gitignore`).
`wall-bumper`, `pegboard-hygrometer-holder`, `sander-vac-adapter`, and
`text-stencil` are example outputs of this pipeline and double as reference
implementations of the script conventions below.

**When generating or editing a FreeCAD script, follow the full conventions in
`.claude/skills/cad-forward/SKILL.md`** (or `cad-reverse/SKILL.md` when
reconstructing from an existing model) rather than improvising. The
non-obvious rules that make these scripts work in the FreeCAD GUI:

- Every dimension that can vary is a named alias in a `Spreadsheet::Sheet`
  object (`Parameters`), never a plain Python variable — this is what lets a
  user tweak a cell and hit Ctrl+R to rebuild the model.
- Derived dimensions are spreadsheet formulas (`=B1/2`), not Python
  arithmetic, so geometry expressions stay single-level.
- Geometry is built from `Part::*` document objects (`Part::Box`,
  `Part::Cylinder`, `Part::Cone`, `Part::Sphere`, `Part::Torus`) with
  `setExpression()` binding each property to `Parameters.<alias>`, never raw
  `Part.make*` shapes.
- Booleans are `Part::Cut` / `Part::Fuse` / `Part::Common` /
  `Part::MultiCommon` / `Part::MultiFuse` document objects (chained via
  `Base`/`Tool`), never `.cut()`/`.fuse()` calls on shapes.
- Scripts never export STL — they `doc.saveAs(...)` a `.FCStd` and print a
  `Saved: <path>` line; STL export is a manual step the user does in the
  FreeCAD GUI after reviewing geometry.

## Physical validation

A `.FCStd` looking right in the FreeCAD GUI, or an agent's own headless
geometry/recompute check, is a pre-flight sanity check — not validation.
**For any `/wayfinder` map whose destination concerns a physical part (or
set of parts), the map's actual destination is only reached once a human has
printed the part(s) and confirmed they work.** When charting a new map like
this, its Destination/Notes should say so explicitly, and its final ticket
should be a human task: print it, check fit/function, record the outcome.

The agent never has access to a physical 3D printer, and never will —
starting a print and judging the printed result are permanently human-only
steps. **Slicing is a different story:** it's software, not a physical
device, and the pipeline runs a headless slicer (PrusaSlicer, in the
container) via the `cad-slice` skill — slicing both the reference model and
the reconstruction to G-code and comparing them, feeding mismatches and
slicer diagnostics back into the generated scripts. Don't treat slicing
itself as off-limits; only printer hardware access is the permanent line.

## Container / agent runtime

`containers/` builds the sandbox the CAD agent actually runs in:

- `Dockerfile` — Arch Linux base, installs `dependencies.packages` via
  pacman (notably `freecad`, which provides the `python3` with the
  `FreeCAD`/`Part` modules — FreeCAD scripts will `ImportError` under a
  system Python that isn't this one) and installs the
  `@earendil-works/pi-coding-agent` CLI globally via npm. Runs as an
  unprivileged `cad` user.
- `entrypoint.sh` — runs `envsubst` over `models.json` (copied in as
  `models.json.template`) into `~/.pi/agent/models.json` before handing off
  to `CMD`, so the model provider config is resolved from environment
  variables at container start, not baked into the image.
- `models.json` — currently wires up a single provider, `opencode-zen`
  (`https://opencode.ai/zen/v1`, OpenAI-completions compatible), exposing the
  `big-pickle` model. Requires `OPENCODE_ZEN_API_KEY` in the environment for
  `envsubst` to resolve `${OPENCODE_ZEN_API_KEY}`.
- `install-pi.sh` — an alternate, non-container path for installing
  `pi-coding-agent` into `~/.local` (adds it to `PATH`/`NODE_PATH` via
  `.bashrc`) for running the agent directly on a host instead of in Docker.

## Commands

```bash
# Build the CAD agent container
docker build -t cad-agent containers/

# Run it (needs the model provider key for entrypoint.sh's envsubst step;
# mount the repo so cad-forward/cad-reverse can write into cad-scripts/ on the host)
docker run --rm -it -e OPENCODE_ZEN_API_KEY=<key> -v "$(pwd)":/home/cad/cadlab -w /home/cad/cadlab cad-agent

# Run a FreeCAD script directly (must use FreeCAD's bundled python3,
# available inside the container or wherever the `freecad` package is installed)
python3 cad-scripts/<part-name>/<part-name>.py
```

There are no lint/test commands configured in this repo.
