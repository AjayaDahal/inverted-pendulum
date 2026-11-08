# Slicing

Every print file is made from the command line and checked before it is printed. One printer
(Anycubic Kobra S1, 0.4 mm nozzle, 250 mm bed), two materials, one per plate. The slicer is
Anycubic Slicer Next 2.0.0.3 (set `PENDULUM_SLICER` if it is not at
`C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe`); the setup is the VTOL project's.

## What to print from

| File | What it is |
|---|---|
| `3mf/to_print_kobra_s1.3mf` | only the parts still to print, both materials in one project: filament 1 PLA (blue), 2 PETG (orange), one material per bed, the PETG beds first and then the PLA ones; beds marked OPTION only if you need them |
| `3mf/complete_project_kobra_s1_pla.3mf` | the three PLA plates as named plates, in print order: open, pick a plate, slice, send |
| `3mf/complete_project_kobra_s1_petg.3mf` | the three PETG plates the same way (the third, the encoder coupler, is optional) |
| `3mf/s1_<material>_plates/<plate>.3mf` | one plate per project, same content |
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
   about z; footprints (convex hulls) go on largest first at the lowest, then leftmost free spot,
   6 mm apart and 10 mm inside the bed, and the layout is centred. Deterministic: the gate and the
   viewer recompute it.
3. `make_slicer_profiles.py`: the settings in `slicer_profiles/`, each self-contained (the CLI
   does not follow `inherits`).
4. `slice_all.py`: every part and every plate is first written as a 3MF project (parts where they
   print, every setting on board), then that 3MF is sliced on its own (`--arrange 0`, each copy its
   own object, so one failed part can be cancelled on the printer). Each G-code file ends with
   `; pendulum_stl_sha256 = ...`, the hash of the STLs (and places) it was sliced from, and its
   3MF carries the same hash, so the gate tells current files from stale ones without file times
   (git keeps none).
5. `make_projects.py`: the two complete projects, assembled from the plates' 3MFs unchanged.
   `--verify` (run by `build_all.py`) slices each plate of each project again and compares it with
   that plate's G-code. The slicer's CLI crashes on a named plate, so it slices a copy with the
   names blanked.
6. `make_to_print.py`: the one project of the parts still to print. It drops the parts you keep
   (`HAVE`) and the other sensor's, puts `MAYBE` parts on beds of their own, and packs the rest
   first-fit, largest first, one material per bed (`plates.py`'s layout): the PETG beds first, then
   the PLA ones, each named with its material ("PETG 1/2"). Each bed is a project with both
   filaments: PLA objects on filament 1, PETG on 2 with the PETG process's one change (35 % infill)
   set on each object; the filaments get their own colours and the prime tower is off (no bed
   mixes them); the beds are then assembled like
   the complete projects. `--verify` (run by `build_all.py`) slices each bed of the project, and
   the same bed again on its own with its material's presets: same grams, same bed and nozzle
   temperatures. A PETG bed's G-code selects filament 2 (`T1`): on the printer, map each
   filament to the spool that holds it.

`python scripts/slice_all.py <part or plate> ...` re-slices only those; the stamp is the STL's
hash only, so after a profile change re-slice everything.

## Settings

| | PLA | PETG |
|---|---|---|
| Parts | carriage plate, pivot bridge, clamp column, arm and tip, switch blocks, tray, AS5600 adapter | motor and idler mounts, sliders, sleeve, pulleys and flanges, belt jaw, bumpers, hub, magnet cap, clips, coupler |
| Why | stiffer: the parts that must not bend | heat next to the motor, wear, clamped threads |
| Process | `PLA @pendulum`: 0.2 mm layers, 4 walls, 5 top and bottom layers, 25 % gyroid | `PETG @pendulum`: the same with 35 % gyroid |
| Filament | Anycubic's Generic PLA for the S1, 205 °C (215 °C first layer), bed 60 °C | 255 °C, bed 75 °C |

Both start from the installed slicer's "0.20mm Standard @Anycubic Kobra S1 0.4 nozzle". The bed
temperature is set for every plate type, so the build plate chosen on the printer does not
matter. Supports are off, and the parts are laid out to print without them: overhangs are
bridges (the idler mount prints upside down, its slider windows' tops bridge 32 mm), teardrop
holes or 45° chamfers and gussets (the idler mount's web, the clamp's flare on all four sides);
the coupler prints on its side so its flex slots stand upright. The gate checks it (`overhang`,
below). The process
prints no brim; the three parts that stand tall on a small base, `idler_mount`, `belt_clamp`
and `switch_mount`, get a 5 mm brim on their own object from the print table. The 287 mm
`pendulum_arm` lies diagonally on the 250 mm bed.

## What the gate checks

`python scripts/check_parts.py` (also in CI, on the committed files), checks `bed`, `overhang` and
`files`:

- Every print-ready part fits the bed with 5 mm to spare on each side and stands on z = 0; every
  plate keeps its parts 10 mm inside the bed; every copy in the print table is on exactly one
  plate.
- Every print-ready part, sliced into 0.2 mm layers, prints without supports: nothing starts in
  mid-air, nothing held on one side reaches more than 3 mm past the layer below (beyond a 45°
  step), and no bridge spans more than 34 mm.
- All 27 jobs (21 parts, 6 plates): the G-code exists and its stamp is the current STLs' hash;
  it names the right printer and process presets and filament type and has supports off; its 3MF exists
  and carries the same stamp; each object has a brim exactly when the print table gives it one.
- No stray G-code or 3MF files; the complete projects match their plates file for file; the
  to-print project was built from the current parts, layout, choices and presets, and each of its
  beds holds one material, every object on that material's filament, every copy once.
- `tracker.md` (masses and times from the G-code footers), `BOM.md` and the viewer's manifest are
  current.

Not checked: print quality. Print the first plate and test-fit the saddles on the top end bars
with T-nuts before printing the rest (`tracker.md`).
