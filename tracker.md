# Print tracker

Kobra S1, one material per plate: open `3mf/s1_<material>_plates/<plate>.3mf` in Anycubic Slicer
Next (or the complete project, `3mf/complete_project_kobra_s1.3mf`: every plate, PETG and PLA, one
plate per job), slice, send. Masses and times are the slicer's. Edit only the Status column.
Only the parts you still need, both materials in one project: `3mf/to_print_kobra_s1.3mf`
(`scripts/make_to_print.py` lists what it leaves out). In those two projects filament 1 is PLA and
2 is PETG: a PETG plate selects filament 2, so map it to the PETG spool when you send it.

## Before the first print

- [x] The frame: 686 x 193 x 319 mm (your photos and tape), set in `scripts/params.py`.
- [x] The belt: 175 teeth (1400 mm), your count, and `BELT_TEETH` is set to it.
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

| # | Plate | Material | Parts | Filament | Time | Status |
|---|---|---|---|---|---|---|
| 1 | `petg_1_belt_drive` | PETG | motor_mount, idler_mount, clamp_jaw, 2 x idler_slider, idler_sleeve, 4 x rod_bumper, 3 x cable_clip (motor mount, idler mount and sliders, belt jaw, bumpers, clips) | 168 g | 6.6 h | to print |
| 2 | `petg_2_pulleys_pivot` | PETG | motor_pulley, idler_pulley, 2 x pulley_flange, pendulum_hub, magnet_cap (both pulleys and their front flanges, pendulum hub, magnet cap) | 80 g | 3.5 h | to print |
| 3 | `pla_1_carriage_plate` | PLA | carriage_plate (carriage plate) | 107 g | 4.3 h | to print |
| 4 | `pla_2_bridge_clamp_tray` | PLA | pivot_bridge, belt_clamp, electronics_tray, 2 x switch_mount, as5600_mount (pivot bridge, belt clamp, electronics tray, switch blocks, AS5600 adapter) | 217 g | 8.7 h | to print |
| 5 | `pla_3_arm` | PLA | pendulum_arm, pendulum_tip (pendulum arm (diagonal) and tip cap) | 41 g | 1.7 h | to print |
| 6 | `petg_3_option_encoder` | PETG | coupler (only for a 600 P/R optical encoder instead of the AS5600) | 5 g | 0.3 h | optional |

**Totals** (without the optional encoder coupler): PLA 364 g, 14.7 h; PETG 248 g, 10.1 h; 24.8 h in all.

## Reminders for print time

- PETG: dry the spool first (wet PETG strings into the nut pockets and holes), 75 C bed on the
  textured PEI plate; PLA: 60 C. The 3MFs carry these.
- PLA on the long plates: keep the chamber from warming up (the PLA preset runs the exhaust fan;
  open the lid if it still gets warm): warm PLA softens and can clog the nozzle.
- A 5 mm brim on each part that stands tall on a small first layer, carried in its 3MF:
  `belt_clamp`, `idler_mount`, `idler_sleeve`, `switch_mount`, `pendulum_tip`, `magnet_cap`. Cut each brim off with a sharp blade held flat against the part: the sleeve's ends take
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
