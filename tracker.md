# Print tracker

Kobra S1, one material per plate: open `3mf/s1_<material>_plates/<plate>.3mf` in Anycubic Slicer
Next (or the complete project for that material, `3mf/complete_project_kobra_s1_<material>.3mf`,
one plate per job), slice, send. Masses and times are the slicer's. Edit only the Status column.

## Before the first print

- [ ] Measure the frame and set `FRAME_L`, `FRAME_W`, `FRAME_H`, `ROD_SPACING` in `scripts/params.py`
      (DESIGN.md, "Measure first"); run `python scripts/build_all.py`.
- [ ] Read the belt's marking: HTD 5M, 15 mm wide? Closed loop: its length must be 1214-1254 mm,
      or use it as an open belt (cut it once, both ends in the clamp).
- [ ] Print `petg_1_belt_drive` first: check the motor mount and idler mount on the top end bars
      and the T-nuts before printing the rest.
- [ ] Check your T-nuts: the saddles bolt into the top end bars' 40 mm faces. Drop-in (roll-in)
      T-nuts go in from the side; slide-in ones mean loosening one end of each bar.

## Plates

| # | Plate | Material | Parts | Filament | Time | Status |
|---|---|---|---|---|---|---|
| 1 | `petg_1_belt_drive` | PETG | motor_mount, idler_mount, clamp_jaw, 2 x idler_slider, idler_sleeve, 4 x rod_bumper, 3 x cable_clip (motor mount, idler mount and sliders, belt jaw, bumpers, clips) | 137 g | 5.3 h | to print |
| 2 | `petg_2_pulleys_pivot` | PETG | motor_pulley, idler_pulley, 2 x pulley_flange, pendulum_hub, magnet_cap (both pulleys and their front flanges, pendulum hub, magnet cap) | 65 g | 3.0 h | to print |
| 3 | `pla_1_carriage_plate` | PLA | carriage_plate (carriage plate) | 151 g | 5.9 h | to print |
| 4 | `pla_2_bridge_clamp_tray` | PLA | pivot_bridge, belt_clamp, electronics_tray, 2 x switch_mount, as5600_mount (pivot bridge, belt clamp, electronics tray, switch blocks, AS5600 adapter) | 214 g | 8.5 h | to print |
| 5 | `pla_3_arm` | PLA | pendulum_arm, pendulum_tip (pendulum arm (diagonal) and tip cap) | 41 g | 1.7 h | to print |
| 6 | `petg_3_option_encoder` | PETG | coupler (only for a 600 P/R optical encoder instead of the AS5600) | 5 g | 0.3 h | optional |

**Totals** (without the optional encoder coupler): PLA 405 g, 16.2 h; PETG 202 g, 8.4 h; 24.6 h in all.

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
