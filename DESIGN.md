# Design

Every number here comes from `scripts/params.py` (geometry) and `parts/sim.json` (dynamics); the
gate (`scripts/check_parts.py`) checks them. Coordinates: x along the rails (+x = idler end, −x =
motor end), y from the front (−) to the back (+), z up from the desk; origin at the centre of the
frame's footprint.

## Key numbers

| | |
|---|---|
| Frame (yours, estimated) | 560 × 280 × 300 mm, 2020 posts and bottom members, 2040 top end bars on edge |
| Rails (yours) | 2 × 8 mm × 600 mm rods on SK8 supports, 180 mm apart, axes 320 mm above the desk |
| Carriage | 4 × SC8UU under a 150 × 226 × 8 mm printed plate; 0.83 kg moving, belt and spinning parts included |
| Travel | ±178 mm to the bumpers (356 mm), limit switches trip at ±174, firmware keeps to ±168 |
| Belt | HTD 5M, 15 mm; both pulleys 30 teeth (pitch Ø 47.75 mm, 150 mm per turn), axles 226 mm up, 542 mm apart |
| Belt length | closed loop 1234 mm at the nominal idler, 1214–1254 mm within the tensioner's travel; open belt: cut 1244 mm |
| Motor | your NEMA 17 at 1.5 A and 19 V: 10.4 N at the cart up to 1 m/s (torque-speed model), 80 % of it relied on; 21.33 steps/mm at 1/16 microstep |
| Friction | rails 0.8 N, belt 0.3 N, greased idler 0.7 N at 15 N belt tension: 1.8 N at the cart; pivot: goal 0.5 mN m |
| Pivot | 8 mm × 115 mm shaft in 2 × KP08, 70 mm apart, axis 366 mm up; the arm turns 8 mm in front of the frame |
| Pendulum | 20 × 10 mm PLA arm, 300 mm from the axis to the tip; 112 g turning, CG 70 mm out, 1.71 × 10⁻³ kg m² about the axis |
| Sensor | AS5600 (12 bit) with a diametric magnet held 5 mm off the steel shaft's end, or a 600 P/R optical encoder |
| Control (model) | kick, swing-up, catch, LQR with integral action: upright in 5.7 s (≤ 8.3 s over 48 robustness runs), cart within ±129 mm; balanced, it hunts 1.2° at the pivot's goal friction |
| Firmware | `firmware/pendulum`: Arduino Uno / Nano or ESP32, FastAccelStepper, 200 Hz |
| Prints | 21 part files, 6 plates: PLA 405 g / 16.2 h, PETG 202 g / 8.4 h |

## Measure first

The frame's size was estimated from the photos. Before printing, measure and put these in
`scripts/params.py`, then run `python scripts/build_all.py`; the gate re-checks every clearance:

| Name | What to measure | Estimate | Slack in the design |
|---|---|---|---|
| `FRAME_L` | length between the end frames' outer faces | 560 | the pulleys follow the end frames |
| `FRAME_W` | width across the posts' outer faces | 280 | bridge slides ±10 mm: 260–300 wide fit |
| `FRAME_H` | desk to the top of the top end bars | 300 | everything is placed from the bars |
| `ROD_SPACING` | rod centre to rod centre | 180 | SC8UU holes slotted ±5 mm: 170–190 fit |
| `ROD_L` | rod length | 600 | |
| belt | marking on its back; closed loop or cut | HTD 5M-15 | loop 1214–1254 mm, or open |

## How the belt runs now

<img src="renders/05_belt_plane_cut.png" alt="Cut on the belt plane: motor pulley at the left, idler at the right, the clamp column from the carriage down to the upper run">

The belt is a vertical loop in **one plane, the frame's centre line (y = 0)**, round two equal
pulleys whose axles sit at the **same height (z 226)**, so both runs are level and parallel to the
rails, and the clamp grips the upper run in that same plane, under the carriage's centre (no twist
on the carriage). The pulleys stay where yours were, in the end frames under the 2040 top end
bars, so the belt length hardly changes.

**Motor end** (`motor_mount`, PETG). A saddle wraps the −x top end bar from below: a cheek on each
of its 40 mm faces (two M5 + T-nuts each) and a web under it. The motor hangs under the web, its
face on a 7 mm plate with the four M3 heads sunk 3.2 mm so the pulley's back flange (1 mm away)
clears them, between two side walls and on a floor: it cannot twist under belt pull. The shaft
points forward to the pulley; the body sits behind (+y), clear of the carriage.

**Pulleys** (`motor_pulley`, `idler_pulley`, PETG). 30 teeth, HTD 5M grooves (circular, 2.2 mm deep),
17 mm toothed width for the 15 mm belt, a 27 mm flange printed on each and a second flange
(`pulley_flange`) pressed on the front boss after assembly, so the belt has a flange on both sides
with 1 mm to spare. The motor pulley has a D bore whose flat faces a radial M3 × 12 set screw: its
head is sunk below the teeth, its nut captive in a slot under the front flange. Tighten it before
pressing the flange on. The idler turns on `idler_sleeve`.

**Idler end** (`idler_mount`, `idler_slider` × 2, PETG). The same saddle on the +x top end bar, with
two cheeks either side of the idler. Each cheek has a window in which a slider runs along x; the
M5 × 40 axle passes slider – sleeve – slider. An M3 × 30 from an outboard lug into each slider
pulls it out:

1. Grease the sleeve (a drop of any grease or oil: it is a plain bearing). Leave the axle nut
   finger-tight. Turn both tension screws evenly until the lower run sags about 9 mm when you hang
   100 g from its middle (200 g: 18 mm). That is 15 N: enough, as the belt only has to stay
   taut under the motor's largest pull (~4 N each side); more only loads the idler's plain
   bearing, which the motor then has to drag (REPORT.md, P2).
2. Run the cart by hand from end to end. If the belt creeps towards one flange, give that side's
   screw a quarter turn more (the axle squares itself to the belt) and repeat.
3. Tighten the axle nut: it clamps the sliders' flanges against the cheeks. The sleeve takes the
   clamping, so the pulley still turns freely.

**Clamp** (`belt_clamp` PLA, `clamp_jaw` PETG). The upper run is 82 mm below the carriage plate, so
the clamp is a box column (40 × 24 mm, 3 mm walls, flared 45° into the jaw seat) on four M3 × 16
from the plate's top. The belt lies in a 16 mm channel under a flat ceiling on its back; the jaw
comes up from below with 14 HTD tooth seats in phase with the belt's teeth and pulls up on four
M3 × 12 into nuts in the column's side walls. An open belt goes in from both ends, about 30 mm
(6 teeth) each; a closed loop passes straight through. Nothing slips and there is no play
between the cart and the belt.

**Lower run** passes 30 mm under the jaw's screw heads. The cart never reaches the pulleys: the
SC8UU blocks stop on the bumpers first.

## Carriage

<img src="renders/08_carriage.png" alt="Carriage: plate on four SC8UU blocks, the pivot bridge with both KP08s, the sensor tower, the hub and arm in front">

- `carriage_plate` (PLA, 8 mm): four SC8UU blocks underneath (16 × M4 × 10, heads sunk; holes
  slotted ±5 mm in y so the plate fits rods 170–190 mm apart without binding: set the blocks on the
  rods, then tighten). Four M5 nuts in pockets underneath take the bridge; four M3 counterbores take
  the clamp. Two zip-tie bridges at the back edge hold the sensor lead.
- `pivot_bridge` (PLA): carries both KP08s in line (4 × M5 × 16, nuts in pockets underneath), the
  front one over the plate's front edge. Its side flanges are slotted ±10 mm (4 × M5 × 20): slide it
  until the arm turns 8 mm in front of the frame's front face. At its back end the 5 mm **sensor
  tower** stands on the shaft's axis.

## Pendulum

- Shaft: 8 mm × 115 mm steel, through both KP08s (their set screws hold it) into the hub.
- `pendulum_hub` (PETG): split below the bore, one M3 × 20 pinch screw; the arm in a 25 mm socket
  with 2 × M3 × 20 through.
- `pendulum_arm` (PLA, prints diagonally): 20 × 10 mm, its 20 mm in the plane it swings in;
  `pendulum_tip` caps it (M3 × 20 pin; room for washers if you want more tip mass: re-run `sim.py`
  with the new mass).
- It turns a full circle at every cart position: the hub, arm and tip stay in front of the frame
  (y −162 to −144) and the tip clears the desk by 64 mm when it hangs (gate: `pendulum`).
- **Pivot friction** decides how still it balances. While the pivot's bearings stick, the pendulum
  moves with the cart, so a balanced pendulum hunts: about 2.9° and 36 mm peak to peak per mN m
  of friction, and the controller can do little about it (REPORT.md, P16). The swing-up copes with up to
  2.5 mN m; the goal is 0.5 mN m (1.2° and 14 mm). Two KP08 inserts with rubber seals are often
  1-2 mN m, so before the first run:
  - free the inserts: pry the seals off (a small screwdriver under the lip), wash the grease out
    with isopropyl alcohol, one drop of light oil;
  - loosen the KP08 bolts and re-tighten them with the shaft turning (the two blocks in line);
    the set screws must not push the shaft off-centre;
  - measure with the firmware's `f` test (lift the pendulum 30-40°, let go): it prints the
    friction and the hunting to expect, and re-centres hanging on the true vertical. By eye,
    0.5 mN m is about 20 full swings from 30° before it stops; 2.5 mN m, 4.
- **Keep clear:** the arm sweeps a 600 mm circle in front of the frame at any cart position: x
  ±480 mm, 63 to 670 mm above the desk, and its tip reaches 4 m/s. Nothing in that disc while it
  runs; keep the power switch in reach.

## Angle sensor

<img src="renders/09_sensor.png" alt="Sensor tower: the AS5600 board on its adapter, facing the magnet cap on the shaft's end">

**AS5600 (default).** `magnet_cap` (PETG) goes on the shaft's back end (M3 × 8 set screw) with the
6 × 2.5 mm diametric magnet glued in its pocket, on the axis, 5 mm of plastic away from the
shaft's end: steel close behind the magnet pulls its field in, and the reading gets weaker and
less linear (REPORT.md, P7). `as5600_mount` (PLA) bolts to the
tower's front face (2 × M3 × 12, nuts in the tower's back) and carries the board on four raised,
slotted pads (M2.5 self-tapping, or M3, in the board's corner holes, 18–26 mm apart), chip
towards the magnet, 1.5 mm air gap. Solder its header facing forward (or use the side pads), and
tie its DIR pin to GND: left floating on some boards, it flips the angle's direction at random.

**600 P/R optical encoder (option).** Leave out the cap and the adapter; bolt the encoder to the
tower's back face (3 × M3 into its holes on a 28–32 mm circle, its boss through the tower's
window) and join the shafts with `coupler` (PETG, slotted beam coupling: it takes up the
misalignment between the KP08s and the encoder's bearings). The viewer's "optical encoder" button
shows it.

## Travel ends and homing

`rod_bumper` collars (4, PETG, M3 × 12 clamp) sit against the SK8s' inner faces: the SC8UU blocks
stop on them at ±178 mm. A `switch_mount` on each top end bar (one M5 into a T-nut, keyed in the
bar's top slot) holds a mechanical endstop level with the plate; its roller trips at ±174 mm.

Homing: move −x slowly to the −x switch, back off 5 mm, set x = −169 (the trip point less the
back-off); then centre. Keep the controller within ±168 mm.

## Control

The model (`scripts/sim.py`) is the cart-pole of this machine: cart 0.72 kg + belt 0.08 kg + motor
rotor and pulleys 0.03 kg reflected = 0.83 kg; pendulum 112 g with its CG 70 mm from the axis and
1.71 × 10⁻³ kg m² about it (sliced masses, steel shaft, screws). Natural frequency 6.7 rad/s. The
firmware runs the same controller (`firmware/pendulum/controller.h`, line for line: the gate
replays simulated runs through it and requires the same commands).

- **Input = cart acceleration,** at most 4.68 m/s², speed at most 1 m/s. A stepper sets motion,
  not force: the force each run needs (the motion plus 1.8 N of friction at the cart) is checked
  at every step against the motor's torque-speed curve at 1.5 A and 19 V (10.4 N up to 1 m/s),
  80 % of it relied on. The margin never falls below 0.30 N.
- **Start:** when the pendulum has rested near hanging for 0.25 s, a kick: 3.0 m/s² for 65 ms one
  way, then the other.
- **Swing-up:** the cart's speed is set to
  v = −0.222 tanh(53 (E − E_ref)/(m g l)) tanh(15.3 sin(θ + 0.037 θ̇)) m/s, fading to nothing
  near the travel ends, and tracked with u = 31.8 (v − ẋ) − 3.7 x. Its acceleration then pumps
  energy in like the classic law (it follows −θ̇ cos θ), while the cart's speed and travel stay
  bounded. E_ref is 0.128 m g l above the upright rest energy, to make up for pivot friction.
- **Catch:** within 39° of upright while θ + θ̇/ω₀ is under 0.133 rad: the pendulum is coasting
  into the top, so little is left to correct and the cart does not saturate.
- **Balance:** LQR with integral action on [x, ẋ, θ, θ̇, ∫x] (θ = 0 up, positive towards +x),
  Q = diag(2580, 10.1, 109, 4.68, 25.6), R = 1.39: **u = −K s, K = [−45.5, −23.9, −71.7, −10.8,
  −4.30]** (SI units, u in m/s²). The integral takes up an error in the upright calibration.
  Back to the swing-up past 45°.
- **Rate:** θ̇ from successive readings through a first-order filter (α = 0.9 per 5 ms). One
  AS5600 count in a period reads as 0.31 rad/s, so the command ripples while it balances (about
  1 m/s² RMS, 2 N peak to peak at the belt): a hum, inside the force budget (the plot below).
- **Pivot friction:** balanced, the pendulum hunts by an amount set by the pivot's stick-slip:
  2.9° and 36 mm peak to peak per mN m (0.15° and 1 mm without friction). Other weights, a
  model-based observer and friction compensation were tried; none changes it by more than about
  10 %. So the pivot has a goal, 0.5 mN m (1.2° and 14 mm), the gate holds the hunting there, and
  the firmware's `f` test measures the real pivot ("Pendulum").
- **Result:** from hanging still at the goal friction, upright in 5.7 s, the cart within ±122 mm.
  It must work on 48 robustness runs: pendulum mass and inertia ±20 %, CG ±15 %, cart +20 %; delay
  from the angle reading to the motor 8–20 ms; pivot friction 0–2.5 mN m; upright error ±1°;
  AS5600 or the 600 P/R encoder; each run from hanging still, with a 0.7 rad/s push once it
  balances. Every run swings up by 8.3 s, holds and recovers, the cart within ±129 mm. On 260
  random scenarios it was not tuned on, 258 did.

<img src="renders/52_sim_swingup.png" alt="Simulated run from hanging still: kick, swing-up, catch, push; pendulum angle, cart position, force needed and available">

## Electronics and firmware

`electronics_tray` (PLA) lies on the desk behind the frame, hooked to the back long member (2 ×
M5 into T-nuts in its outer slot), with M3 slots for the stepper-driver carrier and the
controller and zip-tie slots. Run the motor and switch leads along the frame in `cable_clip`s
(M5 + T-nut into any slot). Take the sensor lead from the carriage's zip-tie bridges up and over in
a loose loop to the tray: allow 400 mm of slack for the full travel.

| Wiring | Arduino Uno / Nano | ESP32 |
|---|---|---|
| Driver STEP / DIR / EN | 9 / 8 / 7 (STEP on 9 or 10 only) | 25 / 26 / 27 |
| Limit switches −x / +x, normally closed to GND | 4 / 5 | 32 / 33 |
| AS5600 SDA / SCL | A4 / A5 (board on 5 V) | 21 / 22 (board on 3.3 V) |
| or the 600 P/R encoder A / B | 2 / 3 | 18 / 19 |

- **Driver:** 1.5 A, 1/16 microstepping (A4988: MS1-MS3 high), its heatsink on, and a 47-100 µF
  capacitor across its motor supply if the carrier has none. Set the current with Vref: A4988
  Vref = 8 × R_sense × 1.5 A, so 0.82 V with 0.068 Ω sense resistors and 1.2 V with 0.1 Ω (read
  yours); DRV8825 0.75 V. Below about 1.3 A the motor runs short of force (REPORT.md, P1).
- **Supply:** the 19 V laptop brick. At 12 V the motor loses force above ~0.8 m/s.
- **Switches** wired normally closed: a broken wire then reads as pressed and stops the cart.
- **Sensor lead:** SDA and SCL each twisted with a ground, away from the motor wires; over about
  30 cm, set `I2C_HZ` to 100000 at the top of `pendulum.ino`.
- **Firmware:** `firmware/pendulum` (Arduino IDE or arduino-cli; library FastAccelStepper from the
  Library Manager). It builds for the Uno, Nano and ESP32. `config.h` is generated from this
  design (`scripts/make_firmware.py`); your wiring and the two direction settings are at the top
  of `pendulum.ino`. An STM32 board does not run FastAccelStepper.

**First power-on** (serial monitor at 115200; one letter per command, `?` lists them):

1. `i`: both switches read ok; press each by hand and it reads PRESSED.
2. `m`: the sensor report: magnet found, AGC mid-range; turn the pendulum by hand and the angle
   follows. Any key stops the report.
3. Clamp the frame to the desk (REPORT.md, P11). Pendulum hanging, nothing in its circle.
4. `h`: homes slowly to the −x switch. If it heads for +x instead, it stops at that switch and
   tells you to set `DIR_HIGH_MOVES_PLUS` to false.
5. `c`: with the pendulum hanging still: this is its zero, every session.
6. `d`: nudges the cart and checks the angle's direction; if it is reversed it says so (set
   `ANGLE_SIGN` to -1) and uses the right one until reset.
7. `f`: lift the pendulum 30-40° and let go. It prints the pivot's friction (goal 0.5 mN m) and the
   hunting to expect, and re-centres hanging on the true vertical. Over 2.5 mN m, free the pivot
   first ("Pendulum").
8. `r`: kicks, swings up and balances. `s` stops; `t` streams telemetry (ms, x mm, v mm/s, angle,
   command, mode) to plot. It stops by itself on a limit switch, past the soft limit, or when
   the sensor fails to answer.

## Assembly order

1. **Measure** (above), rebuild, print `petg_1_belt_drive` and check the saddles on the bars.
2. **Motor end.** Drop four T-nuts into the −x top end bar's 40 mm faces, slide the saddle up under
   the bar, bolt it (M5 × 10). Motor into the U from behind, four M3 × 8 from the front.
3. **Motor pulley.** M3 nut into its slot, pulley onto the shaft with the screw on the flat, axles
   flush; tighten; press on the front flange (a drop of CA).
4. **Idler end.** Saddle on the +x bar as above. Idler: sleeve into the pulley, front flange on,
   then slider – sleeve – slider on the M5 × 40, nut finger-tight; tension screws in from the lugs.
5. **Carriage.** SC8UU blocks on the rods; plate on them (M4 × 10, loose), slide the cart end to end
   and tighten the screws with the blocks parallel. It must then run end to end with a light push
   and not tighten anywhere: if it binds near one end, the rods are not parallel; move an SK8
   (REPORT.md, P13). Bumpers on the rods against the SK8s.
6. **Clamp.** Nuts into the column's flange pockets and side slots; column under the plate (4 × M3 ×
   16 from the top). Belt round both pulleys, its upper run into the channel; jaw up from below
   (4 × M3 × 12). An open belt: both ends in the channel, teeth in the seats.
7. **Tension** (above).
8. **Pivot.** M5 nuts into the bridge's pockets; KP08s on (M5 × 16); bridge on the plate (M5 × 20,
   washers), slid so the arm will turn 8 mm in front of the frame. Shaft through both KP08s, hub on
   its front end, magnet cap on its back end; KP08 set screws, then the hub's pinch screw. Arm into
   the hub (2 × M3 × 20), tip on.
9. **Sensor.** AS5600 on the adapter, adapter on the tower, 1.5 mm from the magnet. Free the pivot
   ("Pendulum", pivot friction).
10. **Switches, tray, clips, leads.** Then the first power-on ("Electronics and firmware").
