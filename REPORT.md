# Design review: the machine as built (v0) and this design (v1)

The owner's machine was photographed (25 photos, not published) with an NEC 19 in and an LG 22 in
monitor behind it for scale; the KP08 (55 mm), SK8 (42 mm) and NEMA 17 (42.3 mm) fixed the scale
better than the monitors. `scripts/asbuilt.py` models it (parts/as_built/, the viewer's "as built"
mode) and `scripts/check_parts.py` checks this design. The photos show a 2020 frame with 2040 top
end bars, two 8 mm rods on SK8 supports, a printed carriage plate on four SC8UU blocks, two KP08
pillow blocks, a NEMA 17, two printed pulleys and an HTD belt (read then as 5M, about 15 mm). The
structure was unfinished, and the belt did not run properly. A second set of 20 photos, with a
tape and calipers on the machine, then measured it: the model's frame, rods and belt were wrong,
and the design was rebuilt to the measurements (M1-M4). A third set (6 photos) showed the belt
laid flat and the idler off the machine on its axle (M5, M6).

<img src="renders/00_v0_vs_v1.png" alt="Left: the machine as built with findings A1-A9 marked. Right: this design">

## Current status

| | Finding | Severity | Status |
|---|---|---|---|
| A1 | Idler on two thin rods held at one end | blocking: no belt tension, the belt walks | fixed in v1 (axle held at both ends) |
| A2 | Idler position set by a row of holes | major: no real tension | fixed in v1 (two tension screws) |
| A3 | Motor and idler located from different posts | blocking: belt not in one plane | fixed in v1 (one plane, y = 0) |
| A4 | Pulleys at different heights, the motor's single-flanged | major | fixed in v1 (flanged both sides, same height) |
| A5 | Belt link: ladder bar and a hex key | blocking: slip and backlash | fixed in v1 (stiff column, toothed jaw) |
| A6 | Pivot over the cart's middle | blocking for swing-up | fixed in v1 (pendulum in front of the frame) |
| A7 | No shaft, hub, arm or sensor mount | missing | added in v1 |
| A8 | One limit switch, no hard stops | major | fixed in v1 (bumpers + two switches) |
| A9 | Loose electronics and leads | minor | fixed in v1 (tray, clips, strain relief) |
| G1-G6 | Found by the gate while designing v1 | | all fixed (below) |
| M1-M6 | The measuring photos: frame, rods and belt not as modelled; the belt's teeth and the idler from the third set | major: the parts would not have fitted | fixed: design rebuilt to the measurements (below) |
| O1-O4 | Open: to confirm on the real machine | | open: the frame's height; the belt's teeth to confirm by hand (below) |
| P1-P16 | Premortem: how the finished machine could still fail | | fixed in the design, controller or firmware; P3, P9-P16 also need a check on the machine (below) |

## As built (v0)

**A1. The idler's axle is two thin rods held at one end.** A printed bracket with a row of holes on
the idler-end back post holds the axle: two steel rods of about 1.7 mm, taped together (the idler
off the machine, M6), reaching about 140 mm to the pulley. A taut belt pulls the idler with twice
its tension (both runs): 30 N at the 15 N this design uses. As a cantilever, those rods bend for
good at 2-7 N (mild to spring steel) after deflecting 12-40 mm, so they cannot hold the belt taut,
and the pulley tilts and steers the belt towards one flange and off. *v1:* the idler turns on a
sleeve on an M4 x 50 axle held at both ends, 32 mm apart, by two sliders in the cheeks of a saddle
that wraps the top end bar (`idler_mount`, `idler_slider`, `idler_sleeve`). Under 30 N the M4
(core 3.14 mm, taken as simply supported: the clamped sleeve makes it stiffer) bends 0.02 mm and is
stressed to 79 MPa, a quarter of a grade 4.8 screw's yield; the pulley sits between the supports, so
it does not tilt. An M5 x 50 would give 0.008 mm and 38 MPa: either does, and the M4 leaves the
printed sleeve a 1.7 mm wall (1.2 mm round an M5; an M5 fits once the sliders and sleeve are
drilled 5.2 mm).

**A2. Tension in 6 mm steps.** The axle goes in one of the bracket's holes: no fine tension, no lock,
no way to square the axle. *v1:* each slider has its own M3 tension screw from an outboard lug, so
the axle can be pulled out evenly (tension) or one side more (squaring: the belt runs centred);
the axle bolt then clamps the sliders' flanges against the cheeks.

**A3. Nothing puts the pulleys and the clamp in one plane.** The motor hangs from one post on spacers,
the idler from another post on its own bracket, the belt link from the plate: three separately
located parts. *v1:* the belt's plane is the frame's centre line (y = 0). Both pulleys hang from the
top end bars at the same height, spaced for the closed loop, both mounts take their place from the
same kind of saddle on the bars, and the belt clamp hangs from the carriage's centre. The gate
checks it (`belt`).

**A4. Pulleys at different heights, the motor's with one flange.** The printed pulleys are 20-tooth
8M; the idler has a flange on each side (M6), the motor pulley one, and in the photos the runs
slope. *v1:* new 20-tooth HTD 8M pulleys with a flange on each side (the front
one pressed on after assembly), both axles at z 223, so both runs are level and parallel to the rails;
1 mm between the belt and each flange.

**A5. The belt link slips.** A hollow bar with a ladder of slots hangs from the plate, and a hex key
through a slot holds the belt. No tooth is engaged: the link slips under load and has backlash, and
a thin-walled bar on two screws flexes. Both matter for balancing: the controller's cart position
is the stepper's, and any slip or play is error it cannot see. *v1:* `belt_clamp`, a box column
(40 x 24 mm, 3 mm walls) on four M3 screws from the plate down to the upper run, with a flat ceiling
on the belt's back and `clamp_jaw` underneath: HTD 8M tooth seats in phase with the belt's teeth,
four M3 screws. Open belt ends or a closed loop both clamp.

**A6. The pivot over the cart's middle cannot swing up.** In the latest photos the two KP08s stand in
line on the plate's back half. A pendulum on that axis sits over the carriage, between the rails: it
cannot hang past the plate or the rods, so it can only ever be balanced from upright, by hand. *v1:*
`pivot_bridge` carries both KP08s forward so the arm turns in a plane 8 mm in front of the frame's
front face: a full turn is clear at every cart position, the tip 64 mm above the desk when hanging.

**A7. Missing:** pivot shaft, hub, arm, angle sensor mount. *v1:* 8 mm x 115 mm shaft (offcut or M8
bolt), `pendulum_hub` (split clamp), `pendulum_arm` (20 x 10 mm, 300 mm to the tip), `pendulum_tip`,
AS5600 on an adapter on the sensor tower with `magnet_cap` on the shaft's end, or a 600 P/R optical
encoder on the tower's back with `coupler`.

**A8. No hard stops, one switch.** The carriage's SC8UU blocks run into the SK8 supports. *v1:*
`rod_bumper` collars stop the SC8UU blocks at +-241 mm; a `switch_mount` on each top end bar trips
its switch 4 mm before (+-237); the firmware keeps to +-231.

**A9. Loose electronics.** The driver board, controller and leads lie on the desk; the sensor lead
from the moving cart has no strain relief. *v1:* `electronics_tray` hooked to the back long member,
zip-tie bridges at the plate's back edge, `cable_clip`s in the frame's slots.

**Kept as is:** the frame, rods, SK8 supports, SC8UU blocks, KP08s, motor and belt; the black wedge
parts on the idler-end front post (their purpose is not clear from the photos; nothing in v1
touches them). The pulleys sit near where yours were, spaced for your closed loop (O2).

## Found by the gate while designing v1

| | What | Fix |
|---|---|---|
| G1 | The AS5600 adapter reached 6 mm into the bridge (738 mm3) | adapter starts above the bridge; its screws moved up |
| G2 | The -x switch block's locating lip hit the motor mount's saddle (140 mm3) | lip replaced by a key in the bar's top slot |
| G3 | Clamp screws M3 x 12, arm screws and tip pin M3 x 16 too short for their nuts | M3 x 16, M3 x 20, M3 x 20 |
| G4 | Catching the pendulum at 25 deg sent the cart 280-440 mm: past the stops | swing-up aims slightly above the top and the LQR takes over within 10 deg: worst case 80-90 mm |
| G5 | A bang-bang swing-up lurched the cart at the start and never settled on the top | tanh-softened energy pumping with cart centring (`sim.py`) |
| G6 | The pulley's set screw would have pressed on the round of the shaft | the bore's flat and the motor's flat both face the screw (+x) |

## Checked against the measuring photos

The first model scaled the frame from catalogue parts and monitors in the photos. The second set
of photos put a tape and calipers on the machine. Read from them:

| | The model had | The photos show | Now |
|---|---|---|---|
| M1 | Frame 560 x 280 mm | 686 x 193 mm (tape along a long member and an end bar, photos 9-15) | the design's frame: every part follows it |
| M2 | Rods 180 mm apart | 114 mm between centres (calipers over both rods read 122.09, photo 17; the tape gives about 125 with parallax) | SC8UU holes slotted +-8 mm, so 98-130 fit |
| M3 | HTD 5M belt, 15 mm wide | HTD 8M, 20 mm (calipers read 20.0-20.6; the teeth 8 mm apart against the caliper's scale, photo 22); a closed loop (the owner) | 20-tooth 8M pulleys, a 21 mm clamp channel with 8M seats, the axles spaced for the loop |
| M4 | Limit-switch blocks at y = 50 on the end bars | with the rods 114 apart the SK8s sit at y 36-78 there | blocks at y = 20 |
| M5 | A loop of 175 teeth (1400 mm), assumed from where the old pulleys sat | the loop laid flat (photos 4, 8 of the third set): 180 teeth (1440 mm, a stock 8M length). Counted from the tooth pattern's phase round the unwrapped loop: 180.4 and 180.0-181.0 | `BELT_TEETH` 180: the axles 640 mm apart (were 620), both mounts 10 mm further out |
| M6 | Idler with one flange on a 4 mm rod | 20-tooth 8M, about 58 mm flanges on both sides, on two ~1.7 mm rods taped together (photos 6, 7, 9) | A1 and A4 corrected; it can stay the idler if it fits the cheeks (`make_to_print.py`, `MAYBE`) |

What follows from them: the frame is 126 mm longer, so the cart travels +-241 mm (was +-178). The
pendulum's plane moves 43.5 mm back with the narrower frame, and the plate narrows to 160 mm (was
226). A closed loop fixes the pulleys' spacing: 180 teeth (1440 mm, M5) puts each axle 13 mm
inboard of its end frame's centre line, so the motor and idler mounts carry them on webs under the end bars. The
8M belt (0.19 kg) moves with the cart, and the 20-tooth pulley gives 9.8 N for the motor's torque
(was 10.4 with the 5M): the old controller then failed 20 of its 48 runs on the force budget. It
was re-tuned and checked again on scenarios it was not tuned on (DESIGN.md, "Control").

The photos could not give the frame's height (no photo measures it), still open. The belt's length
is not printed on it (its marking, "113C020189", is a batch number); the third set gave its teeth
(M5).

## Open: to confirm on the real machine

**O1. The frame's height.** Length, width and the rods' spacing are measured (M1, M2); the height is
still the 300 mm estimate. The pendulum's tip clears the desk by 64 mm at 300; on a frame lower than
about 250 mm it would hit. Measure it, set `FRAME_H` and run `build_all.py`: the gate re-checks every
clearance (DESIGN.md, "Measure first").

**O2. The belt's tooth count.** A closed HTD 8M loop, 20 mm wide (M3). Its photos laid flat give 180
teeth (M5), and the design is built for 180. Confirm it by hand (mark one tooth, go round): the
tensioner takes +-2.5 teeth; for more, set `BELT_TEETH` and run `build_all.py`. The gate fails if
the loop cannot fit inside the end frames (over about 187 teeth: then cut it once and
clamp both ends).

**O3. The angle sensor.** The design takes an AS5600 board (corner holes 18-26 mm apart) and its
6 x 2.5 mm diametric magnet, or a 600 P/R optical encoder (38 mm, 6 mm shaft, M3 on 28-32 mm).

**O4. The shaft.** An 8 mm x 115 mm steel rod (or the plain part of an M8 bolt). Printed is not
an option through KP08 set screws.

## Premortem: how it could still fail

Imagined the finished machine on the desk, printed, wired and refusing to balance, then went
looking for why, with the frame's size and the belt left aside (O1, O2). Each cause below was
checked with numbers: most against the simulation, which now models them (`scripts/sim.py`), the
rest on paper. The first version of the controller failed most of them in simulation.

| | Could fail because | Found by | Status |
|---|---|---|---|
| P1 | The motor runs out of force | torque-speed model | fixed: drive point, budget in every run |
| P2 | The idler's plain bearing drags | friction model | fixed: 15 N tension, grease |
| P3 | The swing-up never starts, or stalls below the top | pivot friction in the sim | fixed: kick, new pump law; check: free-swing test |
| P4 | The catch saturates and the cart runs away | delay corners | fixed: catch on the divergent mode |
| P5 | Delay between the angle and the motor | delay corners | fixed: modelled, balance law predicts |
| P6 | An upright calibration error parks the cart off-centre | offset corners | fixed: integral action |
| P7 | The magnet sits on the steel shaft | geometry | fixed: 5 mm plastic spacer |
| P8 | No firmware; the usual stepper library is too slow | step-rate budget | fixed: firmware, replayed by the gate |
| P9 | The sensor lead glitches | wiring review | fixed in firmware; check: wiring |
| P10 | A broken switch wire means no stop | wiring review | fixed: normally closed wiring |
| P11 | The frame walks on the desk | force budget | check: clamp it |
| P12 | The T-nuts cannot get into the bars | assembly review | check: tracker |
| P13 | Rods out of parallel bind the cart | assembly review | check: assembly step 5 |
| P14 | The driver overheats or a supply spike kills it | wiring review | check: heatsink, capacitor |
| P15 | The pendulum hits something or someone | geometry | check: keep-out zone |
| P16 | Balanced, the pendulum hunts | settled state in the sim | fixed: pivot goal, `f` test, gate bound; check: free the pivot |

**P1. The motor runs out of force.** The old check took half the holding torque (8.4 N at the
belt) against what the motion asks plus 1 N of friction, and the worst case already asked
8.6 N. A stepper's force depends on its driver's current and falls with speed: an A4988 left at
a typical 1 A gives 6.5 N (20-tooth 8M pulley), and at 12 V the force collapses above about
0.9 m/s. *Fix:* the model
now has the motor's torque-speed curve at the driver's current and supply (`params.MOTOR`,
`DRIVE`: 1.5 A, the 19 V laptop brick, 80 % of the torque relied on), against the motion plus
the friction at the cart, in every run; the controller's acceleration limit (3.54 m/s² with the
8M drive) comes out of that budget and every run keeps 0.71 N in hand. Setting the driver:
DESIGN.md, "Electronics and firmware".

**P2. The idler drags.** The idler turns on its PETG sleeve, a plain bearing that both belt runs
load. At the 35-40 N the old instructions asked for, a dry sleeve takes 3.7 N of the motor's
force. *Fix:* 15 N of tension (the belt only has to stay taut under the motor's largest pull,
about 4 N a side), set by sag (100 g hung mid-span: 10 mm), and grease on the sleeve: 0.7 N,
counted in the budget with the rails and the belt (1.8 N in all).

**P3. The swing-up never starts, or stalls.** Energy pumping pushes in proportion to the swing, so
from rest it does nothing, and two KP08s with their seals let the pendulum come to rest a few
degrees off vertical. The old simulation started 3 deg off vertical with no pivot friction. With
friction added, the old law never left rest, and a stronger acceleration law ran the cart off
its travel before the pendulum was up. *Fix:* a kick when the pendulum rests near hanging, and a
pump that sets the cart's *speed* in proportion to -sin(theta) (saturated): its acceleration
pumps energy in like the classic law, while the cart's speed and travel stay bounded. Every run
now starts hanging still. *Check:* pivot friction must stay under about 2.5 mN m. At 5 mN m no
swing-up fits in the travel (the pendulum gets half way). The firmware's `f` test measures it
(P16 sets a lower goal).

**P4. The catch saturates.** Catching inside an angle and speed window took the pendulum while it
was still moving fast away from upright; the cart saturated, hit its speed limit and ran off the
end (seen in the delay corners). *Fix:* catch when theta + omega / w0 is small, the pendulum
coasting into the top: little left to correct.

**P5. Delay.** The step generator plans ahead (10 ms in the firmware), and the loop adds up to a
period: 8-20 ms from reading the angle to the motor moving. *Fix:* the model has it, and the
balance law predicts the state over the commands still on their way to the motor.

**P6. Upright calibration error.** Upright is taken as hanging + 180 deg; the sensor's
non-linearity can make that a degree off, and the old LQR then parked the cart about 40 mm off
centre per degree (-2 deg and a push reached the soft limit). *Fix:* integral action on the cart
position; every run has +-1 deg.

**P7. The magnet sits on the steel shaft.** It was 1.4 mm from the shaft's end: steel pulls the
field in, and the angle reads weaker and less linear. *Fix:* 5 mm of plastic between them (the
sensor tower moves back 3.6 mm); the firmware checks the AS5600's magnet status before it runs.

**P8. No firmware, and the usual stepper library is too slow.** A typical sketch with AccelStepper
manages about 4,000 steps/s on an Uno; the cart needs up to 20,000 (1 m/s at 1/16 step). A wrong
motor direction or angle sign makes it fail at once. *Fix:* `firmware/pendulum` (Uno / Nano or
ESP32, FastAccelStepper, built for all three): homing checks the motor's direction against the
switches, the `d` test checks the angle's sign, and it stops on a failed sensor read, a switch or
the soft limit. Its controller is `sim.py`'s, line for line; the gate replays simulated runs
through the compiled C++ and requires the same commands.

**P9. The sensor lead glitches.** I2C over half a metre of flexing lead beside the motor wires
can corrupt reads or hang the bus. *Fix:* a bus timeout, and any failed read stops the cart.
*Check:* SDA and SCL twisted with ground, away from the motor leads, 100 kHz on a long lead; the
AS5600's DIR pin tied to GND (floating on some boards, it flips the direction at random).

**P10. A broken switch wire means no stop.** *Fix:* the firmware expects normally closed
switches, so a broken wire reads as pressed and stops it.

**P11. The frame walks on the desk.** The cart's pushes reach 5.3 N on the frame, about
what a 3.6 kg frame on a smooth desk holds by friction. *Check:* clamp the frame to the desk.

**P12. The T-nuts.** The saddles bolt into the 40 mm faces of the top end bars. Drop-in T-nuts go
in from the side; slide-in ones mean loosening one end of each bar. *Check:* `tracker.md`.

**P13. Rods out of parallel.** The plate bolts rigidly to four blocks: rods that are not parallel
bind at one end, adding friction the budget does not have. *Check:* slide the cart by hand before
fitting the belt (DESIGN.md, assembly step 5).

**P14. Driver heat and supply spikes.** 1.5 A in an A4988 needs its heatsink; without a
47-100 uF capacitor at the driver, spikes on the motor supply can kill it. *Check:* DESIGN.md,
"Electronics and firmware".

**P15. The pendulum hits something.** Its tip sweeps a 600 mm circle in front of the frame, out
to x +-544 mm, at up to 4 m/s. *Check:* keep that disc clear while it runs (DESIGN.md,
"Pendulum").

**P16. Balanced, the pendulum hunts.** The first premortem pass checked that every run stays
balanced, not how still. At the pivot friction the nominal run then had (1.25 mN m), the
pendulum never settled: a 0.8 Hz cycle of 3.5 deg and 44 mm of cart travel, peak to peak, and
7 deg and over 90 mm at 2.5 mN m. Without friction it holds within 0.15 deg. While the pivot's
bearings stick, the pendulum moves with the cart and the balance law walks the cart until they
break free. Other LQR weights, no integral action, a model-based observer, even the true rate,
and friction compensation each changed it by 10 % at most: 2.9 deg and 36 mm per mN m.
Rubber-sealed KP08 inserts are often 1-2 mN m. *Fix:* a goal for the pivot, 0.5 mN m
(`params.PIVOT_FRICTION_GOAL`), which the nominal run now uses and at which the gate bounds the
hunting (1 deg, 15 mm); the firmware's `f` test measures the friction from a free swing and
says what hunting to expect (the gate checks its estimator on simulated swings: within 0.05 mN m),
and re-centres hanging on the true vertical, which friction would otherwise leave off by up to
friction / m g l (1.9 deg at 2.5 mN m). The re-tune for the 8M drive (M3) then showed the gains
do matter after all, for the onset: weighting the cart's speed and the angle heavily and its
position lightly lets the pivot stick less. With those gains it hunts 0.1 deg at 0.5 mN m, 0.9
at 1 and 4.1 at 2.5 (the first controller: 1.2, 2.8 and 7.2), and `tune_controller.py` now ranks
candidates by it. *Check:* free the pivot (DESIGN.md, "Pendulum": seals off, grease out, a drop
of oil, blocks in line) and run `f` before the first run.
