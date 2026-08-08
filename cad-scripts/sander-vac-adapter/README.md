# sander-vac-adapter

A stepped-diameter tube adapter that connects a sander's dust port to a
shop-vac hose of a different diameter.

## Geometry

Two concentric cylindrical sockets (sander end, smaller; vac end, larger)
fused with a conical transition between them to avoid an abrupt step —
abrupt steps are prone to stringing/poor bridging on FDM printers. Each
socket is bored out to its respective inner diameter, and each opening gets
a flared entry chamfer to ease hose/tube insertion.

## Parameters

| Alias | Default | Meaning |
|---|---|---|
| `sander_od` | 34.0 mm | Sander dust-port outer diameter. |
| `vac_od` | 44.75 mm | Shop-vac hose outer diameter. |
| `sander_clearance` | 0.3 mm | Radial clearance added to the sander bore. |
| `vac_clearance` | 0.3 mm | Radial clearance added to the vac bore. |
| `wall` | 3.0 mm | Wall thickness at each socket. |
| `sander_len` | 25.0 mm | Length of the sander-side socket. |
| `vac_len` | 25.0 mm | Length of the vac-side socket. |
| `chamfer_w` | 1.5 mm | Depth of the entry chamfer at each opening. |
| `overlap` | 1.0 mm | Overlap between the two stepped cylinders, guaranteeing a solid union. |

Derived: bore/outer radii for each end, `total_len`, and the transition
cone's geometry (`transition_h`, `transition_z`).

## Build

```
/cad-build sander-vac-adapter.py
```

Output: `/home/developer/cad-output/sander-vac-adapter.FCStd`
