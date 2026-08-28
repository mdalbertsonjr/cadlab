# Research: constraint-based, sketch-first reconstruction for basic-shape and mating-feature fidelity

For [wayfinder ticket #29](https://github.com/mdalbertsonjr/cadlab/issues/29), feeding [#30](https://github.com/mdalbertsonjr/cadlab/issues/30). Triggered by `can-dispenser-ramp` failing human QA ([#13](https://github.com/mdalbertsonjr/cadlab/issues/13)) — and a follow-up QA pass that broadened the diagnosis further. The failure isn't only that mating features (lid-retention groove, inter-part fastener hole) are missing: the taper, main span, and overall envelope shape **themselves** don't visually match the reference model, gestalt-level, not just at the edges. `cad-reverse`'s mesh bounding-box + `Mesh.crossSections()` → `Part::Loft` approach (per #12/#28) isn't reliably reproducing even basic shape, let alone negative-space mating features.

This surfaces facts and trade-offs only — it does not decide anything.

## 1. Detecting negative-space / mating features from a mesh

`cad-reverse`'s current analysis is bounding-box + `Mesh.crossSections()`. Introspecting FreeCAD 1.0.2's actual `Mesh.Mesh` class (`dir(Mesh.Mesh())`, run live against the bundled interpreter — the most primary source available, more current than the wiki) surfaces considerably more:

- **`getSegmentsByCurvature()`** — auto-segments a mesh by curvature. This directly targets "find the groove" style problems: a groove or boss is a local curvature discontinuity, and this method partitions the mesh along exactly those boundaries without hand-picking cross-section planes.
- **`getPlanarSegments()`** — segments the mesh into planar regions. Useful for locating candidate flat mating faces (e.g. a lid's seating face) as a byproduct of segmentation, not manual inspection.
- **`getCurvaturePerVertex()`** — per-vertex curvature values, the finer-grained primitive `getSegmentsByCurvature()` is presumably built on.
- **`unite()` / `intersect()` / `difference()` / `cut()`** — full boolean operations *between two `Mesh` objects*. This is the mechanism for the assembly-context approach in §4: run `partA.intersect(partB)` (or `difference`) between two neighboring parts' meshes to find exactly where they occupy shared space — the mating interface falls directly out of the boolean result, no guessing.
- **`foraminate()`, `nearestFacetOnRay()`** — ray-casting against the mesh. Named for finding perforations/through-holes; a plausible mechanism for locating fastener holes by casting rays and finding ray/mesh misses inside the bounding volume.
- **`getPointNormals()`** — per-point surface normals, useful as an input to curvature/segment analysis or for orienting inferred sketch profiles.

I could not reliably pull full docstrings for these methods in this environment — repeated attempts to introspect `Mesh.Mesh` instance-method `__doc__` crashed the interpreter (segfault) for reasons unrelated to the method semantics themselves (looked like an AppImage/binding quirk, not a documented behavior). The method names above are read directly off the compiled `Mesh` module's own class, which is a primary source in itself (the actual API surface `cad-reverse` would call), but their exact parameter signatures and edge-case behavior would need `help()` inside a stable interactive FreeCAD session, or the FreeCAD C++ source (`src/Mod/Mesh/App/MeshPy.xml` upstream) before any of this is used unattended in a script.

I could not locate a standalone "Mesh scripting" wiki page in the `FreeCAD/FreeCAD-documentation` GitHub mirror (the wiki's live site is behind bot-protection that blocked direct fetching) — the method-name findings above come from direct interpreter introspection, not the wiki.

## 2. A sketch-first, `Sketcher`-as-source-of-truth workflow: this is PartDesign

FreeCAD already ships exactly this workflow as a first-party workbench: **PartDesign**. Per the FreeCAD documentation (`FreeCAD/FreeCAD-documentation` GitHub mirror, `PartDesign_Feature.md`):

> "A PartDesign Feature refers to a 'step' in the modelling process that happens inside of a PartDesign Body."

PartDesign builds a part as a `PartDesign::Body` containing a sequential chain of features, each consuming a `Sketcher::SketchObject` as its defining profile:

- **Additive**: `Pad` (extrude), `Revolution`, `Loft`, `Pipe`/Sweep, plus additive primitives.
- **Subtractive**: `Pocket` (extrude-cut — the direct mechanism for a retention groove), `Groove` (revolve-cut), `Hole` (a purpose-built feature, not a generic cut).

`PartDesign::Hole` (`PartDesign_Hole.md`) is a direct fit for the missing fastener hole this ticket's QA fail identified: "The Hole feature creates one or more holes from a selected sketch's circles and arcs" — you sketch circles at the fastener centers and the feature does the rest, including standard screw-clearance/counterbore/countersink profiles (`Hole Cut Type`) if the real part needs one. `PartDesign::Pocket` (`PartDesign_Pocket.md`) — "cuts solids by extruding a sketch... along a straight path" with a `Through All` / `Dimension` / `Up to Face` depth — is the direct mechanism for a retention groove: sketch the groove's cross-section on the relevant face, cut to a fixed depth.

This is a materially different mechanism from the Loft/Sweep convention decided in #12, not an extension of it: #12's convention uses a bare `Sketcher::SketchObject` only as input geometry to a `Part::Loft`/`Part::Sweep` — the sketch itself is disposable, one profile among possibly several. PartDesign instead makes the sketch (and its constraints) the persistent unit of design intent inside a `Body`, and *composes* features (Pad, Pocket, Hole, Groove, Loft, Sweep — PartDesign has its own Loft/Pipe too) as a history — closer to "start from a base sketch, build the 3D model from the sketch's constraints" as stated in the ticket.

**Headless feasibility (the deciding constraint for this pipeline):** the SKILL.md's existing convention rules out `Draft::Wire` because it throws `ImportError` under a bare `python3 <script>.py` invocation (needs the Gui subsystem). Whether PartDesign has the same problem is not a hypothetical — it's a documented, closed FreeCAD issue, and I reproduced it directly:

- **[FreeCAD/FreeCAD#16407](https://github.com/FreeCAD/FreeCAD/issues/16407)** ("CLI: Crash when `import PartDesignGui` in headless python script"): a user hit `ModuleNotFoundError: No module named 'PartDesign'` running `import PartDesign` from a bare external `python3 script.py`, while the exact same `import PartDesign` worked fine inside FreeCAD's own console (`FreeCADCmd` / `freecad -c`). The root cause, per a maintainer's follow-up comment in that thread (quoted verbatim): the fix is **not** Gui-related at all — it's that the `Mod/` directory (where `PartDesign`, a partially Python-implemented workbench, lives) isn't on `sys.path` by default for an externally-invoked script the way FreeCAD's own launcher sets it up:

  > "needed for PartDesign and other Python modules" — `sys.path.append(FREECAD_MOD_PATH)`, alongside the lib path already needed for `import FreeCAD`.

  A different commenter in the same thread confirms, with a working code sample, that **no Gui import is needed at all**:
  > "You don't need the gui to use Part Design in a headless script." — followed by a working `doc.addObject("PartDesign::Body", ...)` / `doc.addObject("PartDesign::AdditiveBox", ...)` example run via `FreeCADCmd`.

- **I reproduced this directly** against the FreeCAD 1.0.2 AppImage present on this machine, invoking its bundled `python` binary exactly the way this repo's `cad-build` skill does (`python3 <script>.py`, no FreeCAD launcher flags):
  - `import PartDesign` alone: `ModuleNotFoundError: No module named 'PartDesign'` — confirms the failure mode from #16407 reproduces here too.
  - Adding the AppImage's `usr/lib` (for `FreeCAD`/`Part`) and `usr/Mod` (for `PartDesign`) to `sys.path`, plus `LD_LIBRARY_PATH` for the lib dir: imports succeeded, and I built a full `PartDesign::Body` → `Sketcher::SketchObject` → `PartDesign::Pad` → a second face-mounted sketch → `PartDesign::Pocket` (a literal groove cut) chain, recomputed, and got valid single-solid geometry at every step (`Shape.isValid()` true, `len(Shape.Solids) == 1`) — with **no `FreeCADGui`/`PartDesignGui` import anywhere**. `Sketcher::SketchObject` also imported and instantiated cleanly on its own.

  This is a genuinely different failure class than `Draft::Wire`'s: that one needs the Gui subsystem *loaded*, full stop, no workaround short of it. PartDesign only needs its module directory *discoverable* — a `sys.path` fix, not a hard Gui dependency.

  **Caveat — verify inside the actual container before relying on this:** I tested against an AppImage (self-contained, mounts to `/tmp/.mount_*`, python/libs bundled unusually), not this repo's actual Arch/pacman `freecad` package (`containers/Dockerfile`). Arch's pacman packaging installs to standard system paths (`/usr/lib/`, `/usr/share/freecad/Mod` or similar) rather than an AppImage's private mount, so the *exact* extra `sys.path` entries needed — if any are needed at all — will differ, and pacman's `python3` binary (which the container's `cad-build` invokes directly, per AGENTS.md) may already resolve `Mod/` correctly out of the box where the AppImage's did not. The mechanism (Mod-directory discoverability, not Gui) is confirmed; the exact path(s) to add are not, and must be checked with a throwaway script inside the real `cad-agent` container.

## 3. Why the basic envelope/taper shape itself doesn't match — not just missing features

This has a concrete, verified answer, not just a hypothesis: I read `cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.py` (the actual script the failed QA pass was reviewing) rather than only the README's summary, and the taper's construction is:

```python
taper_cut = doc.addObject("Part::Loft", "TaperCut")
taper_cut.Sections = [profile_open, taper_tip]
taper_cut.Solid = True
taper_cut.Ruled = True
```

**Only two sections** — the rectangular open-slot profile at the taper's start, and a single `Part::Vertex` point at its end — for the entire 61.3mm taper span, with `Ruled = True`. Per FreeCAD's own documentation (`Part_Loft.md`):

> "If 'Ruled surface' is 'true' FreeCAD creates a face, a shell or a solid from [ruled surfaces]" — a ruled surface being straight lines connecting corresponding points between profiles.

A ruled loft between exactly two sections is, by construction, a **straight-line interpolation** between them — geometrically a set of 4 straight edges from the rectangle's corners converging linearly to the point, i.e. a pyramid/cone-like taper. This shape is only guaranteed to match the real part at the two measured endpoints; everywhere in between it's linear extrapolation, not measurement — regardless of how many cross-section planes `Mesh.crossSections()` actually sampled during analysis (the README describes using cross-sectioning to find *where* the taper starts, i.e. one boundary decision), none of that intermediate cross-sectional shape data was carried into the `Sections` list the Loft actually built from. If the real taper narrows non-linearly (a curve, a blend, a non-rectangular intermediate profile — plausible for an injection-molded or slicer-modeled dispensing chute), a straight-sided ruled loft between just two profiles will visibly diverge from it, which matches the "gestalt-level wrong" QA finding.

This is corroborated by `Part_Loft_Technical_Details.md`, which describes what changes when more sections **are** used and `Ruled` is off: FreeCAD instead draws **interpolating B-splines through corresponding points of each profile** —

> "imaginary splines the surface is 'made of' are drawn through corresponding points of the corresponding segments"

— i.e. a smooth loft built from several real measured intermediate profiles is constrained to pass through *all* of them, not just extrapolate between two. The same page notes profile count also affects B-spline degree (max degree up to 9 profiles, capped at degree 3 above that "to reduce wiggling") — a secondary tuning concern, not the primary cause here.

**Answering the ticket's framing directly:** this is not strong evidence that loft-from-measurements is *inherently* too lossy regardless of care taken — the tooling already in this pipeline's convention (`Part::Loft` with multiple `Sections`, `Ruled = False`) can track several real intermediate cross-sections if they're actually used. What happened here is that the previous rebuild used the *minimum* viable loft (2 sections, ruled) rather than a denser one built from the cross-section measurements it already had. That said, it's also not purely a "sample more planes" fix in isolation: a denser *ruled* loft is still piecewise-linear between whichever sections you do include, so how many sections is "enough" depends on how curved the real profile is — which circles back to needing either (a) enough real intermediate profiles as Loft sections to make the piecewise-linear approximation good, or (b) a workflow (PartDesign/Sketcher-driven, §2) where the profile *itself* is a designed, constrained 2D curve rather than a handful of sampled points — which is a stronger claim toward "sketch-first," not merely more sampling.

I found nothing in this specific failure pointing to a mesh-import scale/orientation/wrong-axis bug — the script's taper profile sketch has an explicit, deliberate 90° rotation to align its local axes with the model's global Z/Y (`FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90)`), and the constant-cross-section main span (`main_length`) uses a plain `Part::Box`, unaffected by any Loft/orientation math at all — so if the main span *also* reads as gestalt-wrong (the QA feedback doesn't distinguish main span from taper), that would point to the "constant cross-section" measurement itself being wrong (an under-sampled or misjudged `Mesh.crossSections()` read, back in the original #8/#28 analysis, not something visible in the script), a different failure than the taper's. That's not something I can confirm or rule out from the script alone — it would need re-running the cross-section measurement against `Ramp.3mf` with more sample planes and comparing.

## 4. Trade-offs

**Fidelity vs. cost.** PartDesign's Pad/Pocket/Hole/Groove features are purpose-built for exactly the shapes primitives-and-booleans handle clumsily or not at all (a lid-retention groove is a `Pocket`; a fastener hole is a literal `Hole` feature with standard screw profiles built in) — likely *less* code than the current box-cut-plus-loft approach for shapes like this, since the feature does semantic work (e.g. `Hole`'s counterbore/countersink logic) that a hand-rolled `Part::Cut` chain would otherwise reimplement. The cost is conceptual: a `Body`'s features are an ordered history where each one's result depends on the previous (`Tip`), which is a different mental model than the current independently-named `Part::*` object graph, and touches every script this pipeline generates, not just Loft/Sweep cases — `cad-forward` too, per #12's stated scope of "both skills."

**Single-part vs. assembly-level context.** This is the sharper trade-off, and it's inherent to the problem, not a FreeCAD limitation:

- Curvature/planar segmentation (`getSegmentsByCurvature`, `getPlanarSegments`) works from **one part's mesh alone**. It can find "here is a discontinuity, here is a flat region" — candidate features — but nothing in a single mesh says *why* a given groove exists. `can-dispenser-ramp`'s failure is exactly this ambiguity: a human, not curvature math, is what identified "this negative space is where the Lid seats" and "this hole is where the next part bolts on." Cosmetic and functional negative-space features are geometrically indistinguishable from one mesh in isolation.
- Mesh boolean operations (`unite`/`intersect`/`difference` between two `Mesh` objects) **require the neighboring part's mesh too** — but given both, the mating interface is no longer inferred, it's computed directly: intersecting Ramp's mesh against Lid's mesh would show exactly the shared surface, unambiguously. This needs `cad-reverse` to take multiple related meshes as input (or at minimum, the assembly's other files as available context) rather than reconstructing one part in isolation the way it does today — a scope question for #30, since today's `cad-reverse` invocation is explicitly single-file (`<model-file>` argument, plus free-text metadata).

Whichever direction #30 lands on, the metadata `cad-reverse` currently asks the user for (Step 2 of `cad-reverse/SKILL.md`) doesn't currently have a slot for "this part mates with part X at feature Y" — that's a process gap independent of which FreeCAD mechanism (PartDesign vs. extended Part+boolean) ends up producing the geometry.

## Sources

- [FreeCAD-documentation: `PartDesign_Feature.md`](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/PartDesign_Feature.md)
- [FreeCAD-documentation: `PartDesign_Hole.md`](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/PartDesign_Hole.md)
- [FreeCAD-documentation: `PartDesign_Pocket.md`](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/PartDesign_Pocket.md)
- [FreeCAD-documentation: `Headless_FreeCAD.md`](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md)
- [FreeCAD/FreeCAD#16407 — "CLI: Crash when `import PartDesignGui` in headless python script"](https://github.com/FreeCAD/FreeCAD/issues/16407) (root cause + working headless PartDesign example, in comments)
- Live introspection of `Mesh.Mesh` and `PartDesign`/`Sketcher` module behavior, FreeCAD 1.0.2 (AppImage present on this machine), run directly against the bundled interpreter the same way this repo's `cad-build` invokes scripts
- [FreeCAD-documentation: `Part_Loft.md`](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Part_Loft.md)
- [FreeCAD-documentation: `Part_Loft_Technical_Details.md`](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Part_Loft_Technical_Details.md)
- This repo: `.claude/skills/cad-reverse/SKILL.md`, `.claude/skills/cad-build/SKILL.md`, `cad-scripts/can-dispenser-ramp/README.md`, `cad-scripts/can-dispenser-ramp/can-dispenser-ramp-parametric.py` (the actual taper-Loft construction examined in §3), [issue #12](https://github.com/mdalbertsonjr/cadlab/issues/12)
