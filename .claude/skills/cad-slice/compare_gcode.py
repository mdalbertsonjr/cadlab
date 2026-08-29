"""Compare two PrusaSlicer G-code files: a baseline (sliced from the original
reference mesh) and a candidate (sliced from the reconstructed part).

Both files must come from the same PrusaSlicer install and profile — this
comparison is only meaningful for a self-consistent baseline (see
.claude/skills/cad-slice/SKILL.md).

Usage: python3 compare_gcode.py <baseline.gcode> <candidate.gcode>

Exit code 0 = pass, 1 = fail (or unparseable input).
Stdlib only — runs inside the cad-agent container.
"""

import re
import sys

# --- Tolerances (adjust here) -------------------------------------------------
LAYER_COUNT_TOLERANCE = 1        # layers; baseline vs candidate
FILAMENT_TOLERANCE = 0.10        # fraction; total filament used [mm]
TIME_TOLERANCE = 0.10            # fraction; estimated print time [s]
LAYER_BBOX_TOLERANCE_MM = 1.0    # mm; per-layer extrusion bbox edge deviation
LAYER_EXTRUSION_TOLERANCE = 0.15 # fraction; per-layer extrusion path length
# A few layers (first/last, seam shifts) can legitimately disagree; fail only
# if more than this fraction of compared layers is out of tolerance.
MAX_BAD_LAYER_FRACTION = 0.05

G1_RE = re.compile(r"^G1\b")
COORD_RE = re.compile(r"([XYZE])(-?\d+\.?\d*)")
FILAMENT_RE = re.compile(r"^; filament used \[mm\]\s*=\s*([\d.]+)")
TIME_RE = re.compile(r"^; estimated printing time.*=\s*(.+)$")
STABILITY_RE = re.compile(
    r"print warning: Detected print stability issues:.*?(?=\n\S|\Z)", re.DOTALL
)


def parse_stability_warning(log_path):
    """Return PrusaSlicer's 'Detected print stability issues' block from a
    captured --export-gcode stdout log, or None if absent/file missing. This
    is a real, empirically-confirmed PrusaSlicer diagnostic (bridging/overhang
    analysis, on by default) that was previously silently discarded — see
    SKILL.md. Not itself a pass/fail signal: the reference baseline can
    legitimately trigger this too (real unsupported bridging is sometimes
    correct design, not a modeling defect) — only a *difference* between
    baseline and candidate is actionable."""
    if not log_path:
        return None
    try:
        with open(log_path, "r", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    m = STABILITY_RE.search(text)
    return m.group(0).strip() if m else None


def parse_time_to_seconds(text):
    """Parse PrusaSlicer's '1d 2h 3m 4s' style estimate into seconds."""
    total = 0
    for value, unit in re.findall(r"(\d+)\s*([dhms])", text):
        total += int(value) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
    return total


def parse_gcode(path):
    """Return (layers, filament_mm, time_s). Each layer is a dict with
    xmin/xmax/ymin/ymax of extrusion moves and total extrusion path length."""
    layers = []
    current = None
    filament_mm = None
    time_s = None
    x = y = None
    e = 0.0
    relative_e = False

    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith(";LAYER_CHANGE"):
                current = {
                    "xmin": float("inf"), "xmax": float("-inf"),
                    "ymin": float("inf"), "ymax": float("-inf"),
                    "path_len": 0.0,
                }
                layers.append(current)
                continue
            m = FILAMENT_RE.match(line)
            if m:
                filament_mm = float(m.group(1))
                continue
            m = TIME_RE.match(line)
            if m and time_s is None:  # first estimate line (normal mode)
                time_s = parse_time_to_seconds(m.group(1))
                continue
            if line.startswith("M83"):
                relative_e = True
                continue
            if line.startswith("M82"):
                relative_e = False
                continue
            if line.startswith("G92"):
                m = COORD_RE.findall(line)
                for axis, val in m:
                    if axis == "E":
                        e = float(val)
                continue
            if not G1_RE.match(line):
                continue
            coords = dict(COORD_RE.findall(line.split(";")[0]))
            new_x = float(coords["X"]) if "X" in coords else x
            new_y = float(coords["Y"]) if "Y" in coords else y
            de = 0.0
            if "E" in coords:
                new_e = float(coords["E"])
                de = new_e if relative_e else new_e - e
                e = 0.0 if relative_e else new_e
            if de > 0 and current is not None and new_x is not None and new_y is not None:
                # extrusion move: extend the layer bbox and path length
                for px in (x, new_x):
                    if px is not None:
                        current["xmin"] = min(current["xmin"], px)
                        current["xmax"] = max(current["xmax"], px)
                for py in (y, new_y):
                    if py is not None:
                        current["ymin"] = min(current["ymin"], py)
                        current["ymax"] = max(current["ymax"], py)
                if x is not None and y is not None:
                    current["path_len"] += ((new_x - x) ** 2 + (new_y - y) ** 2) ** 0.5
            x, y = new_x, new_y

    # Drop trailing layers with no extrusion at all (e.g. end-gcode artifacts)
    while layers and layers[-1]["path_len"] == 0.0:
        layers.pop()
    return layers, filament_mm, time_s


def pct(a, b):
    return abs(a - b) / b * 100 if b else float("inf")


def main():
    if len(sys.argv) not in (3, 5):
        print(__doc__)
        print("Usage: compare_gcode.py <baseline.gcode> <candidate.gcode> "
              "[<baseline.slice.log> <candidate.slice.log>]")
        return 1
    baseline_path, candidate_path = sys.argv[1], sys.argv[2]
    baseline_log = sys.argv[3] if len(sys.argv) == 5 else None
    candidate_log = sys.argv[4] if len(sys.argv) == 5 else None
    base_layers, base_fil, base_time = parse_gcode(baseline_path)
    cand_layers, cand_fil, cand_time = parse_gcode(candidate_path)

    failures = []
    print(f"Baseline:  {baseline_path}")
    print(f"Candidate: {candidate_path}")
    print()

    # --- Print-stability warning (informational — see parse_stability_warning) ---
    if baseline_log or candidate_log:
        base_warn = parse_stability_warning(baseline_log)
        cand_warn = parse_stability_warning(candidate_log)
        print("== Print-stability warning (PrusaSlicer, informational) ==")
        print(f"Baseline:  {'DETECTED' if base_warn else 'none'}")
        print(f"Candidate: {'DETECTED' if cand_warn else 'none'}")
        if bool(base_warn) != bool(cand_warn):
            print("DIFFERENTIAL: this warning appears on only one side — the "
                  "reconstruction likely introduced (or fixed) a real "
                  "bridging/overhang problem the other doesn't have.")
            print(f"  {'Candidate' if cand_warn else 'Baseline'} warning text:")
            for line in (cand_warn if cand_warn else base_warn).splitlines():
                print(f"    {line}")
        elif base_warn:
            print("Both sides trigger this warning — likely real unsupported "
                  "bridging in the design itself, not a reconstruction defect.")
        print()

    # --- Aggregate gate ---
    print("== Aggregate gate ==")
    print(f"Layer count:      baseline {len(base_layers)}, candidate {len(cand_layers)}")
    if abs(len(base_layers) - len(cand_layers)) > LAYER_COUNT_TOLERANCE:
        failures.append(
            f"layer count differs by {abs(len(base_layers) - len(cand_layers))} "
            f"(tolerance {LAYER_COUNT_TOLERANCE})"
        )
    if base_fil is None or cand_fil is None:
        failures.append("filament-used comment missing from one or both files")
        print(f"Filament [mm]:    baseline {base_fil}, candidate {cand_fil}  (unparseable)")
    else:
        print(f"Filament [mm]:    baseline {base_fil:.1f}, candidate {cand_fil:.1f} "
              f"({pct(cand_fil, base_fil):.1f}% diff)")
        if pct(cand_fil, base_fil) > FILAMENT_TOLERANCE * 100:
            failures.append(
                f"filament used differs {pct(cand_fil, base_fil):.1f}% "
                f"(tolerance {FILAMENT_TOLERANCE * 100:.0f}%)"
            )
    if base_time is None or cand_time is None:
        failures.append("estimated-time comment missing from one or both files")
        print(f"Est. time [s]:    baseline {base_time}, candidate {cand_time}  (unparseable)")
    else:
        print(f"Est. time [s]:    baseline {base_time}, candidate {cand_time} "
              f"({pct(cand_time, base_time):.1f}% diff)")
        if pct(cand_time, base_time) > TIME_TOLERANCE * 100:
            failures.append(
                f"estimated time differs {pct(cand_time, base_time):.1f}% "
                f"(tolerance {TIME_TOLERANCE * 100:.0f}%)"
            )

    # --- Per-layer signal ---
    print()
    print("== Per-layer signal ==")
    n = min(len(base_layers), len(cand_layers))
    bad_layers = []
    max_bbox_dev = 0.0
    worst_ext_ratio = 0.0
    for i in range(n):
        b, c = base_layers[i], cand_layers[i]
        if b["path_len"] == 0.0 and c["path_len"] == 0.0:
            continue
        bbox_dev = max(
            abs(b["xmin"] - c["xmin"]), abs(b["xmax"] - c["xmax"]),
            abs(b["ymin"] - c["ymin"]), abs(b["ymax"] - c["ymax"]),
        )
        max_bbox_dev = max(max_bbox_dev, bbox_dev)
        if b["path_len"] > 0 and c["path_len"] > 0:
            ext_dev = abs(b["path_len"] - c["path_len"]) / b["path_len"]
        else:
            ext_dev = float("inf")
        worst_ext_ratio = max(worst_ext_ratio, ext_dev)
        if bbox_dev > LAYER_BBOX_TOLERANCE_MM or ext_dev > LAYER_EXTRUSION_TOLERANCE:
            bad_layers.append((i, bbox_dev, ext_dev))

    print(f"Layers compared:  {n}")
    print(f"Max bbox deviation: {max_bbox_dev:.2f} mm (tolerance {LAYER_BBOX_TOLERANCE_MM} mm/layer)")
    print(f"Worst extrusion-length deviation: {worst_ext_ratio * 100:.1f}% "
          f"(tolerance {LAYER_EXTRUSION_TOLERANCE * 100:.0f}%/layer)")
    print(f"Out-of-tolerance layers: {len(bad_layers)}/{n} "
          f"(fail threshold {MAX_BAD_LAYER_FRACTION * 100:.0f}%)")
    if bad_layers:
        worst = sorted(bad_layers, key=lambda t: max(t[1], t[2] * 10), reverse=True)[:5]
        for i, bbox_dev, ext_dev in worst:
            print(f"  layer {i}: bbox dev {bbox_dev:.2f} mm, extrusion dev {ext_dev * 100:.1f}%")
    if n and len(bad_layers) / n > MAX_BAD_LAYER_FRACTION:
        failures.append(
            f"{len(bad_layers)}/{n} layers out of tolerance "
            f"(threshold {MAX_BAD_LAYER_FRACTION * 100:.0f}%)"
        )

    print()
    if failures:
        print("VERDICT: FAIL")
        for f_ in failures:
            print(f"  - {f_}")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
