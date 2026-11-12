"""One-off printed fixes for parts printed before a design change, in fixes/ (not part of the
machine, not in the gate).

sc8uu_shims_pla: the first carriage plate (printed 2026-11-11) has 4.2 mm counterbores, so an
M4 x 10 reaches 6.2 mm into an SC8UU and stops on the end of its blind thread before its head
clamps the plate, which then slides (REPORT.md, R15). One shim under each head, in the
counterbore's slot, leaves 3.8 mm in the block; the slot in the shim lets the screw sit anywhere
along the plate's slot. Twenty on one PLA bed: one per screw and four spare.

Run: python scripts/make_fixes.py
"""
import glob
import hashlib
import os
import shutil
import tempfile

import cad
import geom as G
import params as P
import slice_all as SA

OUT = os.path.join(G.ROOT, "fixes")
CB_PRINTED = 4.2                          # the red plate's M4 counterbores
SHIM_T = 2.4                              # 12 layers: 10 - (8 - 4.2) - 2.4 = 3.8 mm into the block
COPIES, COLS, PITCH = 20, 5, (17.0, 33.0)


def sc8uu_shim():
    r_out = P.HEAD["M4"][0] / 2           # 3.5: 0.2 mm inside the counterbore's 3.7
    r_in = P.D_M4 / 2 + 0.05              # 2.3: the plate's 4.5 mm slot, a little open for the print
    s = P.SC_SLOT
    return cad.slot_z(r_out, 0, -s, 0, s, 0, SHIM_T) - cad.slot_z(r_in, 0, -s, 0, s, -1, SHIM_T + 1)


def _slice(stls, gcode, project, stamp):
    """slice_all's two steps (lay out a project 3MF, slice it), writing into fixes/."""
    settings = [os.path.join(SA.PROFILES, SA.MACHINE["s1"]), os.path.join(SA.PROFILES, SA.PROCESS[("s1", "pla")])]
    with tempfile.TemporaryDirectory() as tmp:
        name3 = os.path.basename(project)
        SA._run([SA.SLICER, "--arrange", "0", "--orient", "0", "--ensure-on-bed",
                 "--datadir", os.path.join(tmp, "cfg"), "--load-settings", ";".join(settings),
                 "--load-filaments", os.path.join(SA.PROFILES, SA.FILAMENT["pla"]),
                 "--metadata-name", SA.META_3MF, "--metadata-value", stamp,
                 "--export-3mf", name3, "--outputdir", tmp, *stls], f"{name3}: no 3MF written")
        sliced = os.path.join(tmp, "sliced")
        os.makedirs(sliced)
        SA._run([SA.SLICER, "--slice", "0", "--arrange", "0", "--orient", "0",
                 "--datadir", os.path.join(tmp, "cfg_3mf"), "--outputdir", sliced, os.path.join(tmp, name3)],
                f"{name3}: slicing")
        found = glob.glob(os.path.join(sliced, "*.gcode"))
        if len(found) != 1:
            raise RuntimeError(f"{len(found)} G-code files for {name3}")
        shutil.move(found[0], gcode)
        shutil.move(os.path.join(tmp, name3), project)
    with open(gcode, "a", newline="\n") as f:
        f.write(f"{SA.STAMP}{stamp}\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    stl = os.path.join(OUT, "sc8uu_shim.stl")
    cad.export(sc8uu_shim(), stl)
    tris = G.read_stl(stl)
    cx, cy = SA.bed_centre()
    rows = (COPIES + COLS - 1) // COLS
    with tempfile.TemporaryDirectory() as tmp:
        stls = []
        for k in range(COPIES):
            dx = (k % COLS - (COLS - 1) / 2) * PITCH[0]
            dy = (k // COLS - (rows - 1) / 2) * PITCH[1]
            path = os.path.join(tmp, f"sc8uu_shim_{k + 1}.stl")
            G.write_stl(path, G.transform(tris, None, (cx + dx, cy + dy, 0.0)))
            stls.append(path)
        with open(stl, "rb") as f:
            stamp = hashlib.sha256(f.read() + f"{COPIES}x{COLS}@{PITCH}".encode()).hexdigest()
        gcode = os.path.join(OUT, "sc8uu_shims_pla.gcode")
        _slice(stls, gcode, os.path.splitext(gcode)[0] + ".3mf", stamp)
    g, mins, _ = SA.stats(gcode)
    into = 10.0 - (P.PLATE_T - CB_PRINTED) - SHIM_T
    print(f"wrote fixes/sc8uu_shims_pla.3mf and .gcode: {COPIES} shims, {SHIM_T} mm, {g:.1f} g, {mins:.0f} min; "
          f"an M4 x 10 then goes {into:.1f} mm into the SC8UU (thread taken as {P.SC8UU['thread']:g})")


if __name__ == "__main__":
    main()
