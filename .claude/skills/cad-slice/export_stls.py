"""Export both sides of a cad-slice comparison to STL, and assert their
bounding boxes agree before any slicing happens.

Usage (inside the cad-agent container, which has FreeCAD):
    python3 export_stls.py <part.FCStd> <reference-mesh-file> <out-dir>

Writes <out-dir>/candidate.stl (tessellated from the FCStd's Body tip shape)
and <out-dir>/baseline.stl (the reference mesh re-exported as STL), then
compares bounding boxes and exits 1 with both boxes printed if any dimension
differs by more than BBOX_TOLERANCE_MM — a mismatch here means the two models
are not in the same coordinate frame/orientation and slicing them would
produce a meaningless comparison.
"""

import os
import sys

sys.path.append("/usr/lib/freecad/lib")

import FreeCAD  # noqa: E402
import Mesh  # noqa: E402
import MeshPart  # noqa: E402

BBOX_TOLERANCE_MM = 2.0  # reconstruction is envelope-faithful, not surface-exact
LINEAR_DEFLECTION = 0.1  # mm; tessellation fineness for the solid


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 1
    fcstd_path, ref_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    # Candidate: tessellate the built part's final solid
    doc = FreeCAD.openDocument(fcstd_path)
    body = None
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body":
            body = obj
            break
    if body is not None:
        shape = body.Tip.Shape
    else:
        # trivial-primitive/boolean parts: take the last visible shaped feature
        shaped = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
        if not shaped:
            print("No solid geometry found in", fcstd_path)
            return 1
        shape = shaped[-1].Shape
    cand_mesh = doc.addObject("Mesh::Feature", "CandidateMesh")
    cand_mesh.Mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=LINEAR_DEFLECTION)
    cand_path = os.path.join(out_dir, "candidate.stl")
    cand_mesh.Mesh.write(cand_path)
    cand_bb = cand_mesh.Mesh.BoundBox

    # Baseline: re-export the reference mesh as STL
    ref_doc = FreeCAD.newDocument("RefDoc")
    Mesh.insert(ref_path, ref_doc.Name)
    ref_meshes = [o for o in ref_doc.Objects if o.TypeId == "Mesh::Feature"]
    if not ref_meshes:
        print("No mesh found in", ref_path)
        return 1
    if len(ref_meshes) > 1:
        print(f"WARNING: {len(ref_meshes)} meshes in {ref_path}; using the largest")
        ref_meshes.sort(key=lambda m: m.Mesh.Volume, reverse=True)
    base_path = os.path.join(out_dir, "baseline.stl")
    ref_meshes[0].Mesh.write(base_path)
    base_bb = ref_meshes[0].Mesh.BoundBox

    def dims(bb):
        return (bb.XLength, bb.YLength, bb.ZLength)

    print(f"candidate.stl bbox: {dims(cand_bb)}")
    print(f"baseline.stl  bbox: {dims(base_bb)}")
    deltas = [abs(a - b) for a, b in zip(dims(cand_bb), dims(base_bb))]
    if max(deltas) > BBOX_TOLERANCE_MM:
        print(
            f"ORIENTATION/SIZE MISMATCH: bbox dimensions differ by up to "
            f"{max(deltas):.2f} mm (tolerance {BBOX_TOLERANCE_MM} mm). The two "
            f"models are not comparable as-is — check coordinate frame, axis "
            f"convention, and units before slicing."
        )
        return 1
    print(f"Bounding boxes agree within {BBOX_TOLERANCE_MM} mm — OK to slice.")
    print(f"Wrote: {cand_path}")
    print(f"Wrote: {base_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
