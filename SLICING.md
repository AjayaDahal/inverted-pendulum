# Slicing

Every print file is made from the command line and checked before it is printed. One printer
(Anycubic Kobra S1, 0.4 mm nozzle, 250 mm bed), two materials, one per plate. The slicer is
Anycubic Slicer Next 2.0.0.3 (set `PENDULUM_SLICER` if it is not at
`C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe`); the setup is the VTOL project's.

## What to print from

| File | What it is |
|---|---|
| `3mf/to_print_kobra_s1.3mf` | only the parts still to print, both materials in one project: filament 1 PLA (blue), 2 PETG (orange), one material per bed, the PETG beds first and then the PLA ones; beds marked OPTION only if you need them |
| `3mf/complete_project_kobra_s1.3mf` | every plate, PETG and PLA, as named plates in print order (`tracker.md`), one project for the Kobra S1 with the same two filaments: open, pick a plate, slice, send (the sixth, the encoder coupler, is optional) |
| `3mf/s1_<material>_plates/<plate>.3mf` | one plate per project, one material, same content |
| `3mf/s1_<material>/<part>.3mf` | one part per project, for a reprint |
| `gcode/<same folder>/<same name>.gcode` | what slicing that 3MF gives, for printing from a USB stick |

The plates, their parts, masses and times: [`tracker.md`](tracker.md). Start with
`petg_1_belt_drive`, after measuring the frame (`DESIGN.md`, "Measure first").

## Pipeline

`python scripts/build_all.py` runs it all, in this order, then the gate:

1. `make_print_ready.py`: the print table. Each part's material, number of copies, the rotation
   that lays it on the bed (proper rotations only, so nothing is mirrored), brim and per-part
   settings; writes `parts/print_ready/<part>.stl`, centred, standing on z = 0. A part whose surface
   has not changed keeps its file (the CAD kernel re-triangulates a part that only moves), so a new
   frame height does not make its G-code stale.
2. `plates.py`: six plates, one material each. Parts keep their print orientation and only turn
   about z; footprints (convex hulls, grown by the part's brim) go on largest first at the lowest,
   then leftmost free spot, 6 mm apart and 10 mm inside the bed, and the layout is centred.
   Deterministic: the gate and the viewer recompute it.
3. `make_slicer_profiles.py`: the settings in `slicer_profiles/`, each self-contained (the CLI
   does not follow `inherits`).
4. `slice_all.py`: every part and every plate is first written as a 3MF project (parts where they
   print, every setting on board), then that 3MF is sliced on its own (`--arrange 0`, each copy its
   own object, so one failed part can be cancelled on the printer). Each G-code file ends with
   `; pendulum_stl_sha256 = ...`, the hash of the STLs (and places) it was sliced from, and its
   3MF carries the same hash, so the gate tells current files from stale ones without file times
   (git keeps none).
5. `make_projects.py`: the complete project. Every plate of `plates.py`, in print order, as a bed
   with both filaments: PLA objects on filament 1, PETG on 2 with the PETG process's one change
   (35 % infill) set on each object, each object with its own settings from the print table (brims);
   the filaments get their own colours and the prime tower is off (no plate mixes them). `--verify`
   (run by `build_all.py`) slices each plate of the project again and compares it with that plate's
   own G-code: the same grams, the same bed and nozzle temperatures. The slicer's CLI crashes on a
   named plate, so it slices a copy with the names blanked. (In a two-filament project the slicer
   holds PETG to the PLA's flow limit, 8 mm³/s instead of 10: a PETG plate prints the same lines
   about 9 % slower there than from its own file.)
6. `make_to_print.py`: the one project of the parts still to print. It drops the parts you keep
   (`HAVE`) and the other sensor's, puts `MAYBE` parts on beds of their own, and packs the rest
   first-fit, largest first, one material per bed (`plates.py`'s layout): the PETG beds first, then
   the PLA ones, each named with its material ("PETG 1/2"). Each bed is built like the complete
   project's. `--verify` (run by `build_all.py`) slices each bed of the project, and
   the same bed again on its own with its material's presets: same grams, same bed and nozzle
   temperatures. In both projects a PETG bed's G-code selects filament 2 (`T1`): on the printer,
   map each filament to the spool that holds it.

`python scripts/slice_all.py <part or plate> ...` re-slices only those; the stamp is the STL's
hash only, so after a profile change re-slice everything.

## Settings

| | PLA | PETG |
|---|---|---|
| Parts | carriage plate, pivot bridge, clamp column, arm and tip, switch blocks, tray, AS5600 adapter | motor and idler mounts, sliders, sleeve, pulleys and flanges, belt jaw, bumpers, hub, magnet cap, clips, coupler |
| Why | stiffer: the parts that must not bend | heat next to the motor, wear, clamped threads |
| Process | `PLA @pendulum`: 0.2 mm layers, 4 walls (inner ones first), 5 top and bottom layers, 25 % gyroid | `PETG @pendulum`: the same with 35 % gyroid |
| Filament | Anycubic's Generic PLA for the S1, 210 °C (220 °C first layer: its brass-nozzle values), bed 60 °C, exhaust fan 60 % | 255 °C, bed 75 °C |

Both start from the installed slicer's "0.20mm Standard @Anycubic Kobra S1 0.4 nozzle", and print
the walls from the inside out as it does: printed outer wall first, a hole's walls in a bridged
ceiling went down over the pocket below touching nothing, the way the thrust stand's crank failed
(REPORT.md, R1). The bed
temperature is set for every plate type, so the build plate chosen on the printer does not
matter. Supports are off, and the parts are laid out to print without them: overhangs are
bridges (the idler mount prints upside down, its slider windows' tops bridge 32 mm), teardrop
holes or 45° chamfers and gussets (the idler mount's web, the clamp's flare on all four sides);
the coupler prints on its side so its flex slots stand upright; the hub's two arm screws and the
clamp's four jaw screws start their holes over a socket or a nut slot in two one-layer steps, so
each layer bridges. Where a bridged face is a
fit (the slider windows' edges, the hub's socket) it has room for the bridge's sag. The gate checks
it (`overhang` and `air`, below). The process prints no brim; each part taller than the square root
of its first layer's area (`idler_mount`, `belt_clamp`, `switch_mount`, `idler_sleeve`,
`magnet_cap`, `pendulum_tip`) gets a 5 mm brim on its own object from the print table, and the
plates keep their gap from the brims. The 287 mm `pendulum_arm` lies diagonally on the 250 mm bed.

## What the gate checks

`python scripts/check_parts.py` (also in CI, on the committed files), checks `bed`, `overhang`,
`air` and `files`:

- Every print-ready part fits the bed with 5 mm to spare on each side and stands on z = 0; every
  plate keeps its parts and their brims 10 mm inside the bed; every copy in the print table is on
  exactly one plate; every part taller than the square root of its first layer's area has a brim.
- Every print-ready part, sliced into 0.2 mm layers, prints without supports: nothing starts in
  mid-air, nothing held on one side reaches more than 3 mm past the layer below (beyond a 45°
  step), and no bridge spans more than 34 mm.
- Every part's and every plate's G-code (a plate turns its parts and prints them together, so its
  lines differ a little), line by line against the layer below: any line more than 3 mm from the
  layer below, whatever the slicer calls it, spans at most 34 mm between two anchors; and no wall is
  laid in mid-air, with no line under it and none of its own layer beside it yet, unless it runs at
  most 1 mm, stays within 1 mm of the layer below, is a stub of at most 3 mm held at one end, or
  bridges between two anchors. A ring of hole walls over a pocket is such a wall; the raster check
  above reads it as a short ledge.
- All 27 jobs (21 parts, 6 plates): the G-code exists and its stamp is the current STLs' hash;
  it names the right printer and process presets and filament type and has supports off; its 3MF exists
  and carries the same stamp; each object has a brim exactly when the print table gives it one.
- No stray G-code or 3MF files; the complete project and the to-print project were each built from
  the current parts, layouts, choices and presets, and each of their plates holds one material,
  every object on that material's filament with its own settings, every copy once.
- `tracker.md` (masses and times from the G-code footers), `BOM.md` and the viewer's manifest are
  current.

Not checked: print quality. Print the first plate and test-fit the saddles on the top end bars
with T-nuts before printing the rest (`tracker.md`).
