#!/usr/bin/env python3
"""
Generate a parametric spray-paint text stencil using FreeCAD.
All parameters are controlled via command-line arguments.

Usage (inside FreeCAD container):
    freecadcmd /home/developer/cad-output/text-stencil.py -- --lines "HELLO" "WORLD"
    freecadcmd /home/developer/cad-output/text-stencil.py -- \\
        --lines "STENCIL" "TEXT" \\
        --thickness 1.5 \\
        --font-heights 30 20 \\
        --justify center \\
        --margin 8 \\
        --line-gap 5

Notes:
  - Letters with enclosed areas (O, A, B, P, Q, R, D) will have floating islands.
    Add stencil bridges manually in FreeCAD if needed.
  - Quote each line of text separately: --lines "LINE ONE" "LINE TWO"
"""

import argparse
import sys
import os


# ---------------------------------------------------------------------------
# Strip FreeCAD's own arguments when run via `freecadcmd script.py -- ...`
# ---------------------------------------------------------------------------
if "--" in sys.argv:
    sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("--") + 1:]


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a spray-paint text stencil using FreeCAD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  Single line, defaults:
    freecadcmd text-stencil.py -- --lines "HELLO"

  Two lines with independent heights, right-justified:
    freecadcmd text-stencil.py -- --lines "BIG TITLE" "small subtitle" \\
        --font-heights 30 15 --justify right

  Custom thickness, margin, and gap:
    freecadcmd text-stencil.py -- --lines "A" "B" "C" \\
        --font-heights 25 20 15 --thickness 2 --margin 10 --line-gap 4
        """,
    )

    parser.add_argument(
        "--lines", "-l",
        nargs="+",
        required=True,
        metavar="TEXT",
        help="Lines of text to cut into the stencil (quote multi-word lines)",
    )
    parser.add_argument(
        "--thickness", "-t",
        type=float,
        default=1.0,
        metavar="MM",
        help="Stencil plate thickness in mm (default: 1.0)",
    )
    parser.add_argument(
        "--font-heights", "-fh",
        nargs="+",
        type=float,
        metavar="MM",
        help=(
            "Font height for each line in mm.  Provide one value (applied to all lines) "
            "or one value per line.  (default: 20.0 for every line)"
        ),
    )
    parser.add_argument(
        "--justify", "-j",
        choices=["left", "center", "right"],
        default="center",
        help="Horizontal text justification within the plate (default: center)",
    )
    parser.add_argument(
        "--margin", "-m",
        type=float,
        default=5.0,
        metavar="MM",
        help="Margin between text and each plate edge in mm (default: 5.0)",
    )
    parser.add_argument(
        "--line-gap", "-g",
        type=float,
        default=3.0,
        metavar="MM",
        help="Vertical gap between text lines in mm (default: 3.0)",
    )
    parser.add_argument(
        "--font", "-f",
        type=str,
        default="/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        metavar="FILE",
        help="Path to a TrueType (.ttf) font file (default: DejaVuSans-Bold.ttf)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="/home/developer/cad-output/text-stencil",
        metavar="PATH",
        help=(
            "Output base path without extension "
            "(default: /home/developer/cad-output/text-stencil)"
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_FONT_FALLBACKS = [
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
]


def resolve_font(requested: str) -> str:
    if os.path.exists(requested):
        return requested
    for fb in _FONT_FALLBACKS:
        if os.path.exists(fb):
            print(f"  Warning: font '{requested}' not found — using '{fb}'")
            return fb
    print(f"Error: font file not found: {requested}")
    print("Specify a valid TTF file with --font /path/to/font.ttf")
    sys.exit(1)


def resolve_font_heights(font_heights, num_lines: int):
    if font_heights is None:
        return [20.0] * num_lines
    if len(font_heights) == 1:
        return font_heights * num_lines
    if len(font_heights) != num_lines:
        print(
            f"Error: --font-heights must have 1 value or one per line "
            f"({num_lines} lines, got {len(font_heights)} values)"
        )
        sys.exit(1)
    return font_heights


# ---------------------------------------------------------------------------
# Wire topology helpers
# ---------------------------------------------------------------------------

def _classify_wires(wires):
    """
    Separate wires from a makeWireString compound into
    (outer_wire, [inner_wires]) groups.

    Outer wires define the letter boundary; inner wires are enclosed islands
    (e.g. the hole inside 'O' or 'A').
    """
    import Part

    triples = []
    for w in wires:
        try:
            f = Part.Face(w)
            area = abs(f.Area)
            if area > 1e-6:
                triples.append((w, f, area))
        except Exception:
            continue

    if not triples:
        return []

    n = len(triples)
    is_inner = [False] * n

    # A wire is "inner" if a point on it lies inside a wire with larger area
    for i in range(n):
        wi, fi, ai = triples[i]
        if not wi.Vertexes:
            continue
        pt = wi.Vertexes[0].Point
        for j in range(n):
            if i == j:
                continue
            _wj, fj, aj = triples[j]
            if aj > ai and fj.isInside(pt, 0.01, True):
                is_inner[i] = True
                break

    # For each outer wire, collect the inner wires it directly contains
    result = []
    for i, (wo, fo, ao) in enumerate(triples):
        if is_inner[i]:
            continue
        inner = []
        if wo.Vertexes:
            for j, (wi, _fi, _ai) in enumerate(triples):
                if not is_inner[j] or not wi.Vertexes:
                    continue
                pt = wi.Vertexes[0].Point
                if fo.isInside(pt, 0.01, True):
                    inner.append(wi)
        result.append((wo, inner))

    return result


def text_shape_to_solid(string_shape, thickness: float):
    """
    Convert a Part.makeWireString compound into a solid suitable for
    boolean cutting.  Correctly handles letters with enclosed areas by
    building faces with hole wires before extruding.

    Returns a fused solid, or None if no geometry could be produced.
    """
    import Part
    import FreeCAD

    groups = _classify_wires(string_shape.Wires)
    solids = []

    for outer_wire, inner_wires in groups:
        try:
            face = Part.Face([outer_wire] + inner_wires) if inner_wires else Part.Face(outer_wire)
            solid = face.extrude(FreeCAD.Vector(0, 0, thickness))
            solids.append(solid)
        except Exception as exc:
            print(f"    Warning: skipped a glyph face ({exc})")
            continue

    if not solids:
        return None

    # Use a compound instead of fuse: avoids boolean failures when letter
    # outlines touch or nearly-touch (e.g. "LL", "II", tight kerning).
    return Part.makeCompound(solids)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Resolve font and per-line heights before importing FreeCAD
    args.font = resolve_font(args.font)
    args.font_heights = resolve_font_heights(args.font_heights, len(args.lines))

    import FreeCAD
    import Part

    num_lines = len(args.lines)
    print(f"Generating text stencil — {num_lines} line(s), font: {os.path.basename(args.font)}")

    doc = FreeCAD.newDocument("TextStencil")

    # ------------------------------------------------------------------ #
    # Parameters spreadsheet                                               #
    # ------------------------------------------------------------------ #
    sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")

    _row = [1]  # mutable counter via list

    def add_param(label: str, value, alias: str):
        r = _row[0]
        sheet.set(f"A{r}", label)
        sheet.set(f"B{r}", str(value))
        sheet.setAlias(f"B{r}", alias)
        _row[0] += 1

    add_param("thickness",  args.thickness, "thickness")
    add_param("margin",     args.margin,    "margin")
    add_param("line_gap",   args.line_gap,  "line_gap")
    add_param("num_lines",  num_lines,      "num_lines")

    for i, h in enumerate(args.font_heights):
        add_param(f"line_height_{i + 1}", h, f"line_height_{i + 1}")

    # ------------------------------------------------------------------ #
    # Compute plate dimensions from text bounding boxes                   #
    # ------------------------------------------------------------------ #
    raw_shapes = []
    line_widths = []
    line_bb_heights = []  # actual glyph bounding-box heights (may differ from font_heights)
    line_bb_ymins   = []  # actual glyph Y minimums (baseline offset)

    for text, h in zip(args.lines, args.font_heights):
        wire_lists = Part.makeWireString(text, args.font, h, 0)
        flat_wires = [w for char_wires in wire_lists for w in char_wires]
        shape = Part.makeCompound(flat_wires)
        raw_shapes.append(shape)
        bb = shape.BoundBox
        line_widths.append(bb.XLength)
        line_bb_heights.append(bb.YLength)
        line_bb_ymins.append(bb.YMin)
        print(
            f"  Line {len(raw_shapes)}: '{text}'  "
            f"height={h}mm  width={bb.XLength:.2f}mm  bb_height={bb.YLength:.2f}mm"
        )

    max_text_width   = max(line_widths)
    gap_total        = max(0, num_lines - 1) * args.line_gap
    # Use actual bounding-box heights so stacking never overlaps
    total_text_h     = sum(line_bb_heights) + gap_total
    plate_length     = max_text_width + 2 * args.margin
    plate_height_dim = total_text_h + 2 * args.margin

    add_param("plate_length",     plate_length,     "plate_length")
    add_param("plate_height_dim", plate_height_dim, "plate_height_dim")

    print(f"\n  Plate: {plate_length:.2f} mm × {plate_height_dim:.2f} mm × {args.thickness} mm")

    doc.recompute()

    # ------------------------------------------------------------------ #
    # Build geometry directly via OCCT — no parametric document objects  #
    # ------------------------------------------------------------------ #
    # Using Part::Cut / Part::Box document objects causes FreeCAD to      #
    # recompute the boolean on every file open. A compound-of-compounds   #
    # tool (nested letter solids) makes OCCT's boolean engine produce     #
    # zero-volume results silently. Instead we run all boolean ops now    #
    # in Python and store one clean static Part::Feature as the result.   #
    # ------------------------------------------------------------------ #

    # Small epsilon so cutting solids protrude past both plate faces,
    # avoiding coplanar-face boolean failures in OCCT.
    Z_EPS = 0.02

    # --- Plate ---
    result_shape = Part.makeBox(plate_length, plate_height_dim, args.thickness)

    # --- Cut each text line ---
    for i, (text, h, raw_shape, w) in enumerate(
        zip(args.lines, args.font_heights, raw_shapes, line_widths)
    ):
        print(f"\n  Cutting line {i + 1}: '{text}'")
        bb = raw_shape.BoundBox
        bb_h   = line_bb_heights[i]
        bb_min = line_bb_ymins[i]

        # X offset (justification)
        if args.justify == "left":
            x_off = args.margin - bb.XMin
        elif args.justify == "right":
            x_off = plate_length - args.margin - w - bb.XMin
        else:  # center
            x_off = (plate_length - w) / 2.0 - bb.XMin

        # Y offset — stacked by actual bounding-box heights
        accumulated_above = sum(line_bb_heights[:i]) + i * args.line_gap
        y_off = plate_height_dim - args.margin - accumulated_above - bb_h - bb_min

        tool_solid = text_shape_to_solid(raw_shape, args.thickness + 2 * Z_EPS)
        if tool_solid is None:
            print(f"    Warning: no solid produced for line {i + 1} — skipping.")
            continue

        # Flatten: extract all Solids from the compound so we cut with a
        # simple list of solids, not a nested compound-of-compounds.
        letter_solids = tool_solid.Solids if tool_solid.Solids else [tool_solid]

        for letter in letter_solids:
            moved = letter.copy()
            moved.translate(FreeCAD.Vector(x_off, y_off, -Z_EPS))
            try:
                new_shape = result_shape.cut(moved)
                if new_shape.Volume > 1e-6:
                    result_shape = new_shape
                else:
                    print(f"    Warning: cut produced zero volume for a glyph — skipping.")
            except Exception as exc:
                print(f"    Warning: cut failed for a glyph ({exc}) — skipping.")

    # Store the finished stencil as a single static feature
    stencil = doc.addObject("Part::Feature", "Stencil")
    stencil.Shape = result_shape
    print(f"\n  Stencil volume: {result_shape.Volume:.2f} mm³")

    doc.recompute()

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #
    output_path = args.output
    if not output_path.endswith(".FCStd"):
        output_path += ".FCStd"

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    doc.saveAs(output_path)
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
