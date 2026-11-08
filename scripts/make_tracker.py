"""Write tracker.md: the print table (plates in print order, from the sliced G-code: mass, time),
the checklists, and totals. Edit only the Status column and the text in the checklists; the
gate fails when the table is stale.

Run: python scripts/make_tracker.py
"""
import os
import re

import geom as G
import params as P
import plates as PT
import slice_all as SA
from make_print_ready import PARTS

PATH = os.path.join(G.ROOT, "tracker.md")
NOTES = {
    "petg_1_belt_drive": "motor mount, idler mount and sliders, belt jaw, bumpers, clips",
    "petg_2_pulleys_pivot": "both pulleys and their front flanges, pendulum hub, magnet cap",
    "pla_1_carriage_plate": "carriage plate",
    "pla_2_bridge_clamp_tray": "pivot bridge, belt clamp, electronics tray, switch blocks, AS5600 adapter",
    "pla_3_arm": "pendulum arm (diagonal) and tip cap",
    "petg_3_option_encoder": "only for a 600 P/R optical encoder instead of the AS5600",
}
HEAD = """# Print tracker

Kobra S1, one material per plate: open `3mf/s1_<material>_plates/<plate>.3mf` in Anycubic Slicer
Next (or the complete project for that material, `3mf/complete_project_kobra_s1_<material>.3mf`,
one plate per job), slice, send. Masses and times are the slicer's. Edit only the Status column.
Only the parts you still need, both materials in one project: `3mf/to_print_kobra_s1.3mf`
(`scripts/make_to_print.py` lists what it leaves out).

## Before the first print

- [x] The frame: {L} x {W} x {H} mm (your photos and tape), set in `scripts/params.py`.
- [x] The belt: {TEETH} teeth ({LOOP} mm), your count, and `BELT_TEETH` is set to it.
- [ ] Print `petg_1_belt_drive` first: check the motor mount and idler mount on the top end bars
      and the T-nuts before printing the rest.
- [ ] Check your T-nuts: the saddles bolt into the top end bars' 40 mm faces. Drop-in (roll-in)
      T-nuts go in from the side; slide-in ones mean loosening one end of each bar.

## Plates

"""


def _status():
    """Status cells from the current tracker.md, by plate."""
    out = {}
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\| \d+ \| `([a-z0-9_]+)` \|.*\| ([^|]*) \|\s*$", line)
                if m:
                    out[m.group(1)] = m.group(2).strip()
    return out


def render():
    status = _status()
    head = (HEAD.replace("{TEETH}", str(P.BELT_TEETH)).replace("{LOOP}", f"{P.BELT_LOOP:.0f}")
            .replace("{L}", f"{P.FRAME_L:.0f}").replace("{W}", f"{P.FRAME_W:.0f}").replace("{H}", f"{P.FRAME_H:.0f}"))
    rows, tot = [], {"pla": [0.0, 0.0], "petg": [0.0, 0.0]}
    for i, (plate, items) in enumerate(PT.PLATES.items(), start=1):
        g, mins, stamp = SA.stats(PT.gcode_path(plate))
        mat = PT.material(plate)
        fresh = stamp == PT.plate_hash(plate)
        parts = ", ".join(n if c == 1 else f"{c} x {n}" for n, c in items)
        opt = any(PARTS[n]["optional"] for n, _ in items)
        if g is not None and fresh and not opt:
            tot[mat][0] += g
            tot[mat][1] += mins
        gs = f"{g:.0f} g" if g is not None and fresh else "not sliced"
        ts = f"{mins / 60:.1f} h" if mins is not None and fresh else "-"
        st = status.get(plate, "to print" if not opt else "optional")
        rows.append(f"| {i} | `{plate}` | {mat.upper()} | {parts} ({NOTES.get(plate, '')}) | {gs} | {ts} | {st} |")
    table = ["| # | Plate | Material | Parts | Filament | Time | Status |", "|---|---|---|---|---|---|---|"] + rows
    totals = (f"\n**Totals** (without the optional encoder coupler): PLA {tot['pla'][0]:.0f} g, {tot['pla'][1] / 60:.1f} h; "
              f"PETG {tot['petg'][0]:.0f} g, {tot['petg'][1] / 60:.1f} h; "
              f"{(tot['pla'][1] + tot['petg'][1]) / 60:.1f} h in all.\n")
    tail = """
## Reminders for print time

- PETG: dry spool, 75 C bed on the textured PEI plate; PLA: 60 C. The 3MFs carry these.
- The tall parts (`idler_mount`, `belt_clamp`, `switch_mount`) carry a 5 mm brim in their 3MF.
- No part needs supports. The idler mount prints upside down: its slider windows' tops bridge 32 mm.
- Pulleys: print with the integral flange on the bed; press the separate front flange on after
  fitting the set-screw nut (motor pulley) and the sleeve (idler).
- Before assembly: test-fit an M5 T-nut bolt through a saddle cheek, the 8 mm shaft in the hub,
  and an M3 nut in the pulley's nut slot. Ream or file printed holes rather than forcing.
- Grease (or oil) the idler's sleeve before the pulley goes on: it is a plain bearing, and dry it
  takes a share of the motor's force (REPORT.md, P2).
- Free the KP08 inserts before fitting them (seals off, grease out, a drop of light oil) and run
  the firmware's `f` test: the pivot's friction decides how still it balances (REPORT.md, P16).
"""
    return head + "\n".join(table) + "\n" + totals + tail


def current():
    if not os.path.exists(PATH):
        return None
    with open(PATH, encoding="utf-8") as f:
        return f.read()


def main():
    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print(f"wrote tracker.md ({len(PT.PLATES)} plates)")


if __name__ == "__main__":
    main()
