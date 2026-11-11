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
Next (or the complete project, `3mf/complete_project_kobra_s1.3mf`: every plate, PETG and PLA, one
plate per job), slice, send. Masses and times are the slicer's. Edit only the Status column.
Only the parts you still need, both materials in one project: `3mf/to_print_kobra_s1.3mf`
(`scripts/make_to_print.py` lists what it leaves out). In those two projects filament 1 is PLA and
2 is PETG: a PETG plate selects filament 2, so map it to the PETG spool when you send it.

## Before the first print

- [x] The frame: {L} x {W} x {H} mm (your photos and tape), set in `scripts/params.py`.
- [x] The belt: {TEETH} teeth ({LOOP} mm), your count, and `BELT_TEETH` is set to it.
- [ ] Print `petg_1_belt_drive` first: check the motor mount and idler mount on the top end bars
      and the T-nuts before printing the rest.
- [ ] Check your T-nuts: the saddles bolt into the top end bars' 40 mm faces. Drop-in (roll-in)
      T-nuts go in from the side; slide-in ones mean loosening one end of each bar.
- [ ] Before the carriage plate and the pivot bridge: measure your SC8UU's screw holes and the
      KP08's bolt holes against DESIGN.md, "Measure first" (catalogue sizes, not yet measured), or
      print the part's first 2 mm (the slicer's cut tool) and lay it on the blocks.
- [ ] The carriage plate goes on with its engraved lines over the rods and its arrow to the front
      (the pendulum's side): the slots then run across the rods.

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
    brims = ", ".join(f"`{n}`" for n, spec in PARTS.items() if spec["brim"])
    tail = """
## Reminders for print time

- PETG: dry the spool first (wet PETG strings into the nut pockets and holes), 75 C bed on the
  textured PEI plate; PLA: 60 C. The 3MFs carry these.
- PLA on the long plates: keep the chamber from warming up (the PLA preset runs the exhaust fan;
  open the lid if it still gets warm): warm PLA softens and can clog the nozzle.
- A 5 mm brim on each part that stands tall on a small first layer, carried in its 3MF:
  {BRIMS}. Cut each brim off with a sharp blade held flat against the part: the sleeve's ends take
  the axle's clamping, so leave no lip.
- No part needs supports. The idler mount prints upside down: its slider windows' tops bridge 32 mm,
  and the edge each slider rests on has 1 mm of room for that bridge's sag. Each slider must slide
  end to end in its window: if one sticks, file the bridge flat.
- Pulleys: print with the integral flange on the bed; press the separate front flange on after
  fitting the set-screw nut (motor pulley) and the sleeve (idler).
- Before assembly, test-fit: an M5 T-nut bolt through a saddle cheek and each saddle on its bar,
  the 8 mm shaft in the hub and the magnet cap, the motor's shaft in the pulley's D bore, the arm in
  the hub's socket, an M3 nut in the pulley's nut slot, and each front flange on its boss (a press
  fit: push it on square, a drop of CA). Ream or file printed holes rather than forcing.
- Grease (or oil) the idler's sleeve before the pulley goes on: it is a plain bearing, and dry it
  takes a share of the motor's force (REPORT.md, P2).
- Free the KP08 inserts before fitting them (seals off, grease out, a drop of light oil) and run
  the firmware's `f` test: the pivot's friction decides how still it balances (REPORT.md, P16).
""".replace("{BRIMS}", brims)
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
