"""Every number of the inverted pendulum (mm, kg, s, N). Change a number here, then run
`python scripts/build_all.py`.

Coordinates: x along the rails (+x = idler end, -x = motor end), y from the front (-) to the
back (+), z up from the desk. The origin is the centre of the frame's footprint on the desk. The
cart's home is x = 0; the pendulum angle is 0 upright and positive leaning towards +x.

The frame, rails, bearings, motor and belt are the owner's own (no purchases). Their catalogue
sizes are exact. The frame's length and width, the rod spacing and the belt (HTD 8M, 20 mm, a
closed loop) were read from his measuring photos (tape and calipers, 2026-11-06), the belt's
tooth count from his photos of the loop (2026-11-08). Still to measure: the frame's height, and
to confirm by hand: the tooth count (DESIGN.md, "Measure first"). Every printed part that
touches the frame is adjustable over the remaining error.
"""
import math

# ---------------------------------------------------------------- frame (photos 9-15: tape)
FRAME_L = 686.0          # outer length along the rails (end frames' outer faces)
FRAME_W = 193.0          # outer width
FRAME_H = 300.0          # top of the posts and of the 2040 top end bars: an estimate, measure it
EXT = 20.0               # 20-series profile module
SLOT = 6.2               # slot opening of the 20-series profile (B-type, 6 mm)
BAR_H = 40.0             # top end bars: 2040 standing on edge
X_END = FRAME_L / 2 - EXT / 2            # 333: centre plane of each end frame
Y_POST = FRAME_W / 2 - EXT / 2           # 86.5: post centre lines
Z_BAR = (FRAME_H - BAR_H, FRAME_H)       # 260..300: top end bars
Z_BAR_SLOTS = (FRAME_H - 30.0, FRAME_H - 10.0)   # slot centres on the bars' 40 mm faces
X_BAR_IN = X_END - EXT / 2               # 323: inner face of each top end bar
X_BAR_OUT = X_END + EXT / 2              # 343: outer face
Y_FRONT = -FRAME_W / 2                   # -96.5: the frame's front face

# ---------------------------------------------------------------- linear guide (owner's)
ROD_D = 8.0
ROD_SPACING = 114.0                      # centres: calipers across both rods (photo 17) read 122 - 8
Y_ROD = ROD_SPACING / 2
SK8 = dict(w=42.0, h_total=32.8, t=14.0, h=20.0, bolt=32.0)
Z_ROD = FRAME_H + SK8["h"]               # 320
X_SK8_IN = X_END - SK8["t"] / 2          # 326: SK8 inner faces
ROD_L = 2 * (X_END + SK8["t"] / 2)       # 680: at least this, to reach through both SK8s
SC8UU = dict(l=30.0, w=34.0, h=22.0, h_axis=11.0, hole_l=18.0, hole_w=24.0)
BEARING_X = 60.0                         # SC8UU centres at x_cart +-60
Z_PLATE0 = Z_ROD + SC8UU["h_axis"]       # 331: carriage plate underside (SC8UU mounting faces)
PLATE_T = 8.0
Z_PLATE1 = Z_PLATE0 + PLATE_T            # 339
PLATE_X = BEARING_X + SC8UU["l"] / 2     # 75: half-length, flush with the SC8UU ends
PLATE_Y = 80.0                           # half-width: over the SC8UU blocks, behind the pendulum
SC_SLOT = 8.0                            # SC8UU holes slotted +-8 in y: rods 98..130 apart fit

# ---------------------------------------------------------------- motor, belt, pulleys
NEMA17 = dict(side=42.3, length=40.0, hole=31.0, boss=22.0, boss_h=2.0, shaft=5.0, shaft_len=24.0,
              flat=0.5, chamfer=4.0, torque=0.40, rotor=54e-7)   # N m holding torque, kg m^2
BELT = dict(pitch=8.0, width=20.0, thick=5.6, tooth_h=3.38, pld=0.686, kg_per_m=0.13)  # HTD 8M-20 (calipers: 20.0-20.6)
BELT_TEETH = 180                         # the closed loop's teeth: 180 from the photos of the loop (1440 mm): confirm by hand
TEETH = 20
PD = TEETH * BELT["pitch"] / math.pi     # 50.93 pitch diameter
R_TIP = PD / 2 - BELT["pld"]             # 24.78 tip circle of the pulley teeth
GROOVE_R, GROOVE_DEPTH = 3.02, 3.52      # HTD 8M groove (the 5M one x 8/5): circular arc, depth below the tip circle
TOOTH_W = BELT["width"] + 2.0            # 22: toothed width, belt + 2 mm
FLANGE_T = 1.5
R_FLANGE = 30.0
PULLEY_W = TOOTH_W + 2 * FLANGE_T        # 25
R_BELT_BACK = R_TIP + BELT["thick"] - BELT["tooth_h"]   # 27.0
Y_BELT = 0.0                             # belt centre plane = the frame's centre line
# The closed loop sets the axles' spacing; the pulleys sit symmetric about the frame's centre
BELT_LOOP = BELT_TEETH * BELT["pitch"]   # 1440: pitch-line length
C_NOM = (BELT_LOOP - math.pi * PD) / 2   # 640: axle spacing with the idler at its nominal position
X_MOTOR = -C_NOM / 2                     # -320: motor pulley
X_IDLER = C_NOM / 2                      # 320: idler, nominal: the drawings use it
IDLER_TRAVEL = (X_IDLER - 10.0, X_IDLER + 10.0)   # idler axle x range (belt tension)
SADDLE_T = 7.0                           # saddle cheeks and web around each top end bar
SADDLE_WEB = (Z_BAR[0] - 6.0, Z_BAR[0])  # 254..260: web under the bar
Z_PULLEY = SADDLE_WEB[0] - 1.0 - R_FLANGE   # 223: flanges 1 mm under the saddles' webs
Z_RUN_LAND = Z_PULLEY + R_TIP            # upper run's tooth-side face (teeth hang below)
Z_RUN_BACK = Z_PULLEY + R_BELT_BACK      # upper run's back
Z_RUN_TIPS = Z_RUN_LAND - BELT["tooth_h"]
Z_LOW_LAND = Z_PULLEY - R_TIP            # lower run (teeth up)
BELT_LOOP_RANGE = tuple(2 * (x - X_MOTOR) + math.pi * PD for x in IDLER_TRAVEL)
CLAMP_BITE = 30.0                        # belt length each open end has in the clamp
BELT_OPEN_CUT = BELT_LOOP + 2 * CLAMP_BITE - 70.0 + 20.0   # open belt: loop + both bites - clamp + spare

# motor mount: the motor's face on a plate at y 13.5..20.5, body behind it (+y), shaft forward
MOTOR_PLATE_Y = (PULLEY_W / 2 + 1.0, PULLEY_W / 2 + 8.0)
Y_MOTOR_FACE = MOTOR_PLATE_Y[1]

# idler mount: cheeks either side of the pulley with windows for the axle sliders
AXLE_D = 4.0                             # M4 x 50 (an M5 x 50 fits once the sliders and sleeve are drilled 5.2)
IDLER_JOURNAL_R = 3.9                    # the idler turns on its PETG sleeve: a plain bearing of this radius
CHEEK_T = 6.0
CHEEK_Y = (PULLEY_W / 2 + 0.5, PULLEY_W / 2 + 0.5 + CHEEK_T)   # 13..19
SLIDER = dict(x=12.0, z=22.0, axle_dz=-4.0, screw_dz=6.0)       # axle 4 below, screw 6 above its centre
TENSION_SCREW = "M3"

# ---------------------------------------------------------------- carriage: belt clamp
CLAMP = dict(len=70.0, col_x=40.0, col_y=24.0, wall=3.0, chan=BELT["width"] / 2 + 0.5, side=21.0, jaw_base=5.0,
             flange=(60.0, 32.0, 6.0), screw_x=26.0, screw_y=16.0)   # chan: the belt channel's half-width

# ---------------------------------------------------------------- travel
BUMPER_W = 10.0                          # rod collars: the SC8UU blocks stop on them
BUMPER_OD = 20.0
# Stops against the SK8s, or further in if the pulleys sit inboard (a short belt): the clamp keeps
# 3 mm from the nearer pulley's flange
X_STOP = min(X_SK8_IN - BUMPER_W - PLATE_X, C_NOM / 2 - R_FLANGE - CLAMP["len"] / 2 - 3.0)   # 241
X_BUMPER = X_STOP + PLATE_X              # bumpers' inner faces: the SC8UU ends at the stops
X_SWITCH = X_STOP - 4.0                  # limit switches trip 4 mm before the stops
X_SOFT = X_SWITCH - 6.0                  # 231: software limit the controller keeps to

# ---------------------------------------------------------------- pivot, pendulum, sensor
ARM_GAP = 8.0                            # arm to the frame's front face
ARM_T, ARM_W = 10.0, 20.0                # arm section: thickness along y, width along x
Y_ARM = Y_FRONT - ARM_GAP - ARM_T / 2    # -109.5
HUB = dict(len=18.0, r=15.0, socket=25.0)
Y_HUB = (Y_ARM - HUB["len"] / 2, Y_ARM + HUB["len"] / 2)   # -118.5..-100.5
KP08 = dict(l=55.0, j=42.0, a=13.0, base_t=5.5, h=15.0, top=28.5, ring_w=19.0, ring_od=15.0, slot=6.5)
Y_KP_F = Y_HUB[1] + 1.5 + KP08["ring_w"] / 2        # -89.5: front pillow block
KP_SPACING = 70.0
Y_KP_R = Y_KP_F + KP_SPACING                        # -19.5: rear pillow block
BRIDGE_T = 12.0
BRIDGE_X = 32.0                                     # half-width of the pivot bridge
Z_BRIDGE1 = Z_PLATE1 + BRIDGE_T                     # 351
Z_SHAFT = Z_BRIDGE1 + KP08["h"]                     # 366: pivot axis
SHAFT_D = 8.0
TOWER_T = 5.0
Y_SHAFT_END = Y_KP_R + KP08["ring_w"] / 2 + 9.0      # -1: 9 mm behind the rear KP08 for the cap's grip
SHAFT_L = 115.0
Y_SHAFT_START = Y_SHAFT_END - SHAFT_L               # -116
ARM_L = 300.0                                       # pivot axis to the arm's tip
TIP = dict(len=24.0, wall=2.4)                      # tip cap over the arm's end
AS5600 = dict(board=23.0, pcb=1.6, chip=1.5, standoff=6.0, magnet_d=6.0, magnet_t=2.5, gap=1.5)   # adapter 3 + pads 3
MAGNET_SPACER = 5.0                                 # plastic between the steel shaft's end and the magnet
Y_MAGNET = Y_SHAFT_END + MAGNET_SPACER + AS5600["magnet_t"]                                   # magnet face
Y_TOWER = Y_MAGNET + AS5600["gap"] + AS5600["chip"] + AS5600["pcb"] + AS5600["standoff"]   # 17.1
Y_BRIDGE = (Y_KP_F - KP08["a"] / 2 - 1.5, Y_TOWER + TOWER_T)   # -97.5..22.1
BRIDGE_SLIDE = 10.0                                 # the bridge slides +-10 in y: frames 173..213 wide fit
BRIDGE_BOLT_Y = (-PLATE_Y + 12.0, Y_KP_R)           # bridge to plate: 2 x M5 a side, near each KP08
CAP = dict(y0=Y_SHAFT_END - 8.0, y1=Y_MAGNET, r=9.0)                # magnet cap on the shaft end
LPD3806 = dict(d=38.0, length=35.5, shaft=6.0, shaft_len=13.0, boss_d=20.0, boss_h=5.0, pcd=(28.0, 32.0))
COUPLER = dict(y0=Y_SHAFT_END - 8.0, y1=Y_TOWER - 1.0, r=9.0)

# ---------------------------------------------------------------- limit switches, cables, electronics
ENDSTOP = dict(pcb=(40.0, 16.0, 1.6), hole_dx=19.0, sw=(12.8, 5.8, 6.5), lever=14.0)
Y_SWITCH = 20.0                          # on the top end bar, inboard of the SK8 (y 36..78)
TRAY = dict(x=150.0, y=110.0, t=3.0)

# ---------------------------------------------------------------- printing and fits
BED = 250.0                              # Kobra S1
D_M3, D_M4, D_M5 = 3.4, 4.5, 5.5         # clearance holes
D_M3_TAP = 2.6                           # M3 screwed straight into printed plastic
NUT = {"M3": (5.5, 2.4), "M4": (7.0, 3.2), "M5": (8.0, 4.0)}     # across flats, thickness
HEAD = {"M3": (5.6, 3.0), "M4": (7.0, 4.0), "M5": (8.5, 5.0)}    # socket head diameter, height
FIT = 0.2                                # clearance on printed bores and pockets
DENSITY = {"pla": 1.24, "petg": 1.27}    # g/cm^3, solid

# ---------------------------------------------------------------- dynamics (sim.py)
G_ACC = 9.81
CTRL_HZ = 200                            # control loop
# motor: a typical 0.40 N m NEMA 17 (17HS4401 class: 1.7 A, 1.5 ohm, 2.8 mH). Check your motor's label.
MOTOR = dict(i_rated=1.7, r=1.5, l=2.8e-3, pole_pairs=50)
# driver current (A, set with the driver's Vref), supply (V: the laptop brick in the photos gives 19),
# and the fraction of that torque relied on (microstep ripple, resonance)
DRIVE = dict(i_set=1.5, volts=19.0, safety=0.8)
BELT_TENSION = 15.0                      # N per run (DESIGN.md, "How the belt runs now")
# Coulomb friction at the cart, N: four SC8UU (seals), the belt flexing round the pulleys; idler
# journal friction coefficient, PETG on PETG with a drop of grease (dry: ~0.3, twice the drag)
FRICTION = dict(rails=0.8, belt=0.3, idler_mu=0.15)
A_MAX = 5.0                              # m/s^2: the most a controller may ask for; the force budget decides
V_MAX = 1.0                              # m/s cart speed limit (400 rpm)
STEPS_PER_REV = 200 * 16                 # 1/16 microstepping
STEP_RATE_MAX = 40000.0                  # steps/s: FastAccelStepper on an ATmega328P manages ~50k
# What the controller must survive (sim.py, CORNERS): delay from reading the angle to the motor moving
# (the step generator plans 10 ms ahead, plus the loop), Coulomb friction at the pivot (two KP08s:
# the firmware's f test measures it), upright calibration error (sensor non-linearity)
ACT_DELAY = (0.008, 0.020)               # s
PIVOT_FRICTION = 0.0025                  # N m: the swing-up is checked up to this
# Balanced, the pivot's stick-slip makes the pendulum hunt (about 3 deg and 37 mm peak to peak per
# mN m): the goal for the pivot, and the sim's nominal run (DESIGN.md, "Pendulum")
PIVOT_FRICTION_GOAL = 0.0005             # N m
ANGLE_OFFSET = 1.0                       # deg
MASS_VITAMINS_CART = dict(sc8uu=4 * 0.040, kp08=2 * 0.065, screws=0.040, as5600=0.004)
STEEL = 7.85                             # g/cm^3
