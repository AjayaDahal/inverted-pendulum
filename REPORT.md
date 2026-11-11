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
| G1-G8 | Found by the gate while designing v1, and by the owner's slicer | | all fixed (below) |
| M1-M6 | The measuring photos: frame, rods and belt not as modelled; the belt's teeth and the idler from the third set | major: the parts would not have fitted | fixed: design rebuilt to the measurements (below) |
| O1-O4 | Open: to confirm on the real machine | | O1, O2 closed (the frame's height and the belt's teeth, measured); O3, O4 to confirm (below) |
| P1-P16 | Premortem: how the finished machine could still fail | | fixed in the design, controller or firmware; P3, P9-P16 also need a check on the machine (below) |
| R1-R13 | Printing: an audit of the 3MFs and G-code and a premortem of the prints, before the first one; then the first carriage plate, which did not go on its blocks | P1 print: walls laid in mid-air (the thrust stand's crank fault); a printed plate that did not fit | R1-R5 fixed and gated, R11 done; R7-R10 are checks at print time; R12, R13 open: measurements from the owner (below) |

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
one pressed on after assembly), both axles at z 242, so both runs are level and parallel to the rails;
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
front face: a full turn is clear at every cart position, the tip 83 mm above the desk when hanging.

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

## Found by the gate while designing v1, and by the owner's slicer

| | What | Fix |
|---|---|---|
| G1 | The AS5600 adapter reached 6 mm into the bridge (738 mm3) | adapter starts above the bridge; its screws moved up |
| G2 | The -x switch block's locating lip hit the motor mount's saddle (140 mm3) | lip replaced by a key in the bar's top slot |
| G3 | Clamp screws M3 x 12, arm screws and tip pin M3 x 16 too short for their nuts | M3 x 16, M3 x 20, M3 x 20 |
| G4 | Catching the pendulum at 25 deg sent the cart 280-440 mm: past the stops | swing-up aims slightly above the top and the LQR takes over within 10 deg: worst case 80-90 mm |
| G5 | A bang-bang swing-up lurched the cart at the start and never settled on the top | tanh-softened energy pumping with cart centring (`sim.py`) |
| G6 | The pulley's set screw would have pressed on the round of the shaft | the bore's flat and the motor's flat both face the screw (+x) |
| G7 | With supports off, three parts printed in mid-air (the owner's slicer flagged the idler mount): the idler mount's web 29 mm out from its saddle, the clamp's flare 9 mm out across the belt, the coupler's flex slots | a 45° gusset holds the web (the idler saddle now bolts through its outer face only), the flare tapers on all four sides, the coupler prints on its side; the gate's `overhang` check now slices every part |
| G8 | The coupler's set-screw nut pockets were sealed inside it | each opens to the side |

## Checked against the measuring photos

The first model scaled the frame from catalogue parts and monitors in the photos. The second set
of photos put a tape and calipers on the machine. Read from them:

| | The model had | The photos show | Now |
|---|---|---|---|
| M1 | Frame 560 x 280 mm | 686 x 193 mm (tape along a long member and an end bar, photos 9-15) | the design's frame: every part follows it |
| M2 | Rods 180 mm apart | 114 mm between centres (calipers over both rods read 122.09, photo 17; the tape gives about 125 with parallax) | SC8UU holes slotted +-8 mm, so 98-130 fit |
| M3 | HTD 5M belt, 15 mm wide | HTD 8M, 20 mm (calipers read 20.0-20.6; the teeth 8 mm apart against the caliper's scale, photo 22); a closed loop (the owner) | 20-tooth 8M pulleys, a 21 mm clamp channel with 8M seats, the axles spaced for the loop; the idler's sliders tension it, and the belt goes on before the idler's axle and the motor pulley's front flange (DESIGN.md, "Assembly order": the order written for an open belt could not fit a loop) |
| M4 | Limit-switch blocks at y = 50 on the end bars | with the rods 114 apart the SK8s sit at y 36-78 there | blocks at y = 20 |
| M5 | A loop of 175 teeth (1400 mm), assumed from where the old pulleys sat | 175: the owner's count, and the belt is stamped 1400 mm at 8 mm pitch. The photos of the loop laid flat (4, 8 of the third set) had been read as 180, counted from the tooth pattern round the unwrapped loop: about 3 % off, from the loop's perspective; built in for a day, then corrected | `BELT_TEETH` 175: the axles 620 mm apart. A photo cannot count teeth to one: count by hand |
| M6 | Idler with one flange on a 4 mm rod | 20-tooth 8M, about 58 mm flanges on both sides, on two ~1.7 mm rods taped together (photos 6, 7, 9) | A1 and A4 corrected; it can stay the idler if it fits the cheeks (`make_to_print.py`, `MAYBE`) |

What follows from them: the frame is 126 mm longer, so the cart travels +-241 mm (was +-178). The
pendulum's plane moves 43.5 mm back with the narrower frame, and the plate narrows to 160 mm (was
226). A closed loop fixes the pulleys' spacing: 175 teeth (1400 mm, M5) puts each axle 23 mm
inboard of its end frame's centre line, so the motor and idler mounts carry them on webs under the end bars. The
8M belt (0.18 kg) moves with the cart, and the 20-tooth pulley gives 9.8 N for the motor's torque
(was 10.4 with the 5M): the old controller then failed 20 of its 48 runs on the force budget. It
was re-tuned and checked again on scenarios it was not tuned on (DESIGN.md, "Control").

The photos could not give the frame's height (no photo measured it); the owner's tape since has
(O1). The belt is
stamped with its 1400 mm pitch length (the photos showed only its batch number, "113C020189"), and
the owner counted its 175 teeth (M5).

## Open: to confirm on the real machine

**O1. The frame's height.** Closed: 319 mm from the desk to the top of the end bars, the owner's
tape with its hook on the desk, against an end bar (photos of 2026-11-08; two more, with the tape
about 50 mm in front of a rod, read its axis about 10 mm high, as parallax from above makes it).
It had been the 300 mm estimate: everything rises 19 mm, no printed part changes, and the
pendulum's tip clears the desk by 83 mm (64 at 300). The gate re-checks every
clearance (DESIGN.md, "Measure first").

**O2. The belt's tooth count.** Closed: a closed HTD 8M loop, 20 mm wide (M3), of 175 teeth, the
owner's count, and stamped 1400 mm (M5). The design is built for it; the tensioner takes +-2.5
teeth. A different belt: set `BELT_TEETH` and run `build_all.py`. The gate fails if the loop cannot
fit inside the end frames (over about 187 teeth: then cut it once and clamp both ends).

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
8M drive) comes out of that budget and every run keeps 0.68 N in hand. Setting the driver:
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

**P11. The frame walks on the desk.** The cart's pushes reach 5.4 N on the frame, about
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

## Printing: audit and premortem

Before the first print the owner asked for a deep audit of the 3MF files and a premortem of the
prints: does any part need supports, do the settings make sense, how could a print fail? He
remembered the thrust stand, whose crank printed the walls of a hole over its bearing seat and
filled the seat with strands. Method: every extrusion of every part's G-code, whatever the slicer
calls it, was checked against the layer below with a check written for it (the vtol-plane audit's
method, now the gate's `air` check): each stretch over air is followed along its path (is it
anchored at its ends? did a line of its own layer go down beside it first?), and the layers where
it found something were drawn. The processes and filaments were compared key by key with the
installed slicer's own Kobra S1 presets, the projects read plate by plate, each part's height
measured against its first layer, and each fix tried on scratch slices before it was built in.

**The answer: no part needs supports. But six printed the thrust stand's fault, a hole's walls
laid in mid-air over a pocket (R1), and the gate could not see it (R2).** Both are fixed with the
rest below, and every file is re-sliced.

| | Finding | Fix | Status |
|---|---|---|---|
| R1 | **Walls laid in mid-air over pockets, as the thrust stand's crank failed, in six parts.** Where a hole runs up through a bridged ceiling, the slicer printed the hole's walls with nothing under them and nothing beside them yet. Worst: the hub's two arm screws, whose four loops each went down 10 mm above the floor of the socket the arm slides into. Also over the hub's nut pockets, the clamp's jaw-nut slots (0.3 mm of room over a 2.4 mm nut), the carriage plate's and the pivot bridge's M5 nut pockets (19 mm loops), the switch block's M5 counterbore and the motor mount's M3 counterbores: 29 runs that fail the rule in R2, and 1.1 m of wall laid in mid-air across all the parts. Cause: the process printed each outer wall first. It came from the VTOL project's preset, itself from an older Anycubic S1 preset; the installed slicer's own preset prints inner walls first. | Inner walls first and the precise wall off, as in the installed slicer's preset (`make_slicer_profiles.py`): a hole's walls now go down beside the bridge lines printed before them. Same grams, same times. The hub's socket is too deep for that alone (its holes' loops would hang 10 mm over the socket's floor), and the clamp's jaw-nut slots too tight for it (on its plate, turned, the loops round the jaw screws still lay 3.2 mm over the 0.3 mm of room above each nut): their holes now start over the socket or slot in two one-layer steps, a slot right across and then a square, so each layer bridges between held edges (`pendulum_hub`, `belt_clamp`). Tried and dropped: the slicer's own "partially bridged" hole bridging, which left loops crossing its slot, 11-20 mm long and held at one end. After: 134 mm of wall laid in mid-air across all the parts (from 1,087), all of it short, close to the layer below or anchored at both ends. | fixed, gated |
| R2 | **The gate could not see R1.** The `overhang` check rasterises the mesh, and there a ring of hole walls over a pocket is part of a ledge or a bridge inside its limits: a 1.4-2.8 mm ledge over the nut pockets and counterbores, a 20 mm bridge over the hub's socket. | New `air` check: every part's and every plate's G-code, line by line against the layer below (a plate turns its parts and prints them together, and its lines differ a little from the part's own file). Any line more than 3 mm from the layer below, whatever the slicer calls it, spans at most 34 mm between two anchors; no wall is laid in mid-air unless it runs at most 1 mm, stays within 1 mm of the layer below, is a stub of at most 3 mm held at one end, or bridges between two anchors. The old files fail it in all six parts (29 runs); the new ones pass: spans over air up to 31.8 mm (the idler windows), no line held at one end or none more than 2.2 mm out (the switch block's counterbore), and the longest wall laid in mid-air a 20 mm edge of the hub's first step, anchored at both ends. It adds about two minutes to the gate. | fixed, gated |
| R3 | **Bridged faces that are fits.** The idler mount prints upside down, so the edge each slider rests on is the last thing printed over its window: a 32 mm PETG bridge with 0.2 mm of room. Half a millimetre of sag, usual for PETG over that span, would jam the slider at mid-travel. The hub's arm socket the same way: its front face is a 20 mm bridge, 0.2 mm off the arm. | `BRIDGE_SAG`: room for 0.025 mm of sag per mm of span under each, the face on a layer boundary. The windows' lower edges sit 1.0 mm lower (the tension screws, threaded into the sliders, hold them at their height), the socket's front face 0.6 mm further out (the arm screws pull it onto the arm). | fixed |
| R4 | **The saddles had no room on the bars.** Their cheeks stood exactly 20.0 mm apart for the 20 mm top end bars; a printed gap comes out a little small. | `SADDLE_FIT`: 0.1 mm each side; the bolts pull the cheeks onto the bar. | fixed |
| R5 | **Slender parts without a brim.** The idler sleeve stands 26 mm tall on 33 mm² of first layer, the tip cap 26 mm on 367 mm², the magnet cap 16 mm on 186 mm²: levers the nozzle can pry off the bed. Only the three tallest parts had a brim. | A 5 mm brim on every part taller than the square root of its first layer's area (six; the gate's `bed` check holds the rule); the plates keep their 6 mm gap from the brims, and the brims 10 mm inside the bed. | fixed, gated |
| R6 | **Does any part need supports?** | No. The longest bridges are the idler windows' 32 mm (anchored at both ends; at most 34), and nothing held at one end or none lies more than 2.2 mm out from the layer below, in the parts' files or on the plates. Every part's first layer sits on the bed, and nothing starts in mid-air. | verified |
| R7 | **A two-material project selects filament 2 for PETG.** A PETG plate in the complete or the to-print project starts with `T1`. Sent with PLA mapped to filament 2 (or from a USB stick to a printer whose second spool is PLA), it prints the PETG plate in PLA at 255 °C, or the reverse. | `tracker.md` and `SLICING.md`: map filament 2 to the PETG spool when sending; the single-material plate files (`3mf/s1_<material>_plates/`) avoid the question. | check at print time |
| R8 | **Wet PETG** strings into the nut pockets and holes and bridges badly. | `tracker.md`: dry the spool first. | check at print time |
| R9 | **A warm chamber on the long PLA plates** (8.7 h for the second) softens PLA and can clog the nozzle. The PLA preset runs the S1's exhaust fan at 60 %. | `tracker.md`: open the lid if the chamber still warms. | check at print time |
| R10 | **Fits only a print shows.** The front flanges press onto their pulleys' bosses (12.0 mm on 12.0, a press fit by design), the motor pulley's D bore is 5.15 mm for the 5 mm shaft, the magnet cap's bore 8.1 mm for the 8 mm shaft, and each saddle must slide onto its bar. | `tracker.md`: test-fit each before assembly; ream or file rather than force. | check at print time |
| R11 | **One project per printer** (the owner's request): there were two complete projects, one per material. | `3mf/complete_project_kobra_s1.3mf`: every plate, PETG and PLA, in print order, with the to-print project's two filaments (1 PLA, 2 PETG) and each object's own settings (`make_projects.py`). `--verify` slices each plate of it and compares it with that plate's own G-code (grams, bed and nozzle temperatures); the gate audits it plate by plate. One difference, found on the way: in a two-filament project the slicer holds the PETG to the PLA's flow limit (8 mm³/s, not 10), so a PETG plate there prints the same lines about 9 % slower than its own file (6.6 h against 7.2 h for the belt drive): harmless, and `tracker.md` keeps the plates' own times. | done, gated |
| R12 | **The first carriage plate did not go on its blocks** (the owner, 2026-11-11: 106 g of PLA). The premortem asked how a print could fail, not whether a part fits the hardware it bolts to. The plate's SC8UU hole pattern (18 mm along the rod, 24 across, M4) is the catalogue's, never measured on his blocks (R13), and nothing on the plate shows which way it goes on: it is 150 x 160 mm, and its four hole groups sit almost as far apart one way as the other. In his photo the slots seem to run along a rod; on the machine they run across the rods. His old plate, photographed on the machine, has the same groups (about 18 along by 24 across, centred on the rods). | Marks engraved 0.6 mm in the top face: a line over each rod and an arrow to the front edge (`carriage_plate`); `DESIGN.md`, assembly step 5, and `tracker.md` say which way it goes. To confirm: the printed plate turned 90 degrees from the photo. If the screws still miss, the blocks are measured (R13) and the plate redrawn to them. | open: owner to check |
| R13 | **Hardware numbers never measured.** The measuring photos gave the frame, the rods' spacing and the belt; every other part of his hardware went into the design at catalogue sizes, and the premortem did not ask him to check them. Those a printed part depends on: the SC8UU's screw holes (`carriage_plate`: fixed along the rod), the SK8's rod height and the SC8UU's 11 mm (the plate's height, so where the clamp's jaw meets the belt), the KP08's 42 mm bolt spacing and 15 mm shaft height (`pivot_bridge`: fixed M5 holes; in his photo of the old plate its KP08 holes look nearer 39 mm apart, a photo's reading, not a measurement), and the limit-switch board's holes (`switch_mount`: +-1 mm). Standard or adjustable enough: the NEMA 17 (`motor_mount`), the AS5600's pads (18-26 mm), the encoder's (28-32 mm). | `DESIGN.md`, "Measure first": each with what to measure. `tracker.md`: measure before printing the carriage plate and the pivot bridge, or print the part's first 2 mm (the slicer's cut tool, about 10 g) and lay it on the blocks. | open: owner to measure |

Checked and kept: the bed temperature is set for every plate type (PETG 75 °C, PLA 60 °C, the
textured PEI plate selected); PETG at 255 °C and at most 10 mm³/s, fan 40-90 %, off for the first
three layers; PLA 210 °C (220 °C first layer); 0.8 mm retraction, 1 mm wipe, 0.4 mm z-hop; bridges
at 30 mm/s and 90 % flow; 4 walls, 5 top and bottom layers, gyroid infill (25 % PLA, 35 % PETG);
no supports and no arc moves; every object labelled, so one failed part can be cancelled alone.
The other differences from the installed slicer's preset (thin-wall detection, monotonic solid
infill, 0.075 mm elephant-foot compensation among them) are the VTOL project's, proven on the
thrust stand.
