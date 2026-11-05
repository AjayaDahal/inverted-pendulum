"""Every number of the inverted pendulum (mm, kg, s, N). Change a number here, then run
`python scripts/build_all.py`.

Coordinates: x along the rails (+x = idler end, -x = motor end), y from the front (-) to the
back (+), z up from the desk. The origin is the centre of the frame's footprint on the desk. The
cart's home is x = 0; the pendulum angle is 0 upright and positive leaning towards +x.

The frame, rails, bearings, motor and belt are the owner's own (no purchases). Their catalogue
sizes are exact. The frame's size was estimated from photos, with the KP08 (55 mm), SK8 (42 mm)
and NEMA 17 (42.3 mm) as the scale: measure FRAME_*, ROD_SPACING and the belt before printing
(DESIGN.md, "Measure first"). Every printed part that touches the frame is adjustable over the
estimate's error.
"""
import math

# ---------------------------------------------------------------- frame (estimated: measure it)
FRAME_L = 560.0          # outer length along the rails (end frames' outer faces)
FRAME_W = 280.0          # outer width
FRAME_H = 300.0          # top of the posts and of the 2040 top end bars
EXT = 20.0               # 20-series profile module
SLOT = 6.2               # slot opening of the 20-series profile (B-type, 6 mm)
BAR_H = 40.0             # top end bars: 2040 standing on edge
X_END = FRAME_L / 2 - EXT / 2            # 270: centre plane of each end frame
Y_POST = FRAME_W / 2 - EXT / 2           # 130: post centre lines
Z_BAR = (FRAME_H - BAR_H, FRAME_H)       # 260..300: top end bars
Z_BAR_SLOTS = (FRAME_H - 30.0, FRAME_H - 10.0)   # slot centres on the bars' 40 mm faces
X_BAR_IN = X_END - EXT / 2               # 260: inner face of each top end bar
X_BAR_OUT = X_END + EXT / 2              # 280: outer face
Y_FRONT = -FRAME_W / 2                   # -140: the frame's front face

# ---------------------------------------------------------------- linear guide (owner's)
ROD_D, ROD_L = 8.0, 600.0
ROD_SPACING = 180.0
Y_ROD = ROD_SPACING / 2
SK8 = dict(w=42.0, h_total=32.8, t=14.0, h=20.0, bolt=32.0)
Z_ROD = FRAME_H + SK8["h"]               # 320
X_SK8_IN = X_END - SK8["t"] / 2          # 263: SK8 inner faces
SC8UU = dict(l=30.0, w=34.0, h=22.0, h_axis=11.0, hole_l=18.0, hole_w=24.0)
BEARING_X = 60.0                         # SC8UU centres at x_cart +-60
Z_PLATE0 = Z_ROD + SC8UU["h_axis"]       # 331: carriage plate underside (SC8UU mounting faces)
PLATE_T = 8.0
Z_PLATE1 = Z_PLATE0 + PLATE_T            # 339
PLATE_X = BEARING_X + SC8UU["l"] / 2     # 75: half-length, flush with the SC8UU ends
PLATE_Y = 113.0                          # half-width
SC_SLOT = 5.0                            # SC8UU holes slotted +-5 in y: rods 170..190 apart fit

# ---------------------------------------------------------------- travel
BUMPER_W = 10.0                          # rod collars against the SK8s' inner faces
BUMPER_OD = 20.0
X_STOP = X_SK8_IN - BUMPER_W - PLATE_X   # 178: cart centre at the hard stops
X_SWITCH = X_STOP - 4.0                  # limit switches trip 4 mm before the stops
X_SOFT = X_SWITCH - 6.0                  # 168: software limit the controller keeps to

# ---------------------------------------------------------------- motor, belt, pulleys
NEMA17 = dict(side=42.3, length=40.0, hole=31.0, boss=22.0, boss_h=2.0, shaft=5.0, shaft_len=24.0,
              flat=0.5, chamfer=4.0, torque=0.40, rotor=54e-7)   # N m holding torque, kg m^2
BELT = dict(pitch=5.0, width=15.0, thick=3.8, tooth_h=2.06, pld=0.5715, kg_per_m=0.068)  # HTD 5M-15
TEETH = 30
PD = TEETH * BELT["pitch"] / math.pi     # 47.75 pitch diameter
R_TIP = PD / 2 - BELT["pld"]             # 23.30 tip circle of the pulley teeth
GROOVE_R, GROOVE_DEPTH = 1.89, 2.20      # HTD 5M groove: circular arc, depth below the tip circle
TOOTH_W = 17.0                           # toothed width: belt + 2 mm
FLANGE_T = 1.5
R_FLANGE = 27.0
PULLEY_W = TOOTH_W + 2 * FLANGE_T        # 20
R_BELT_BACK = R_TIP + BELT["thick"] - BELT["tooth_h"]   # 25.04
Y_BELT = 0.0                             # belt centre plane = the frame's centre line
X_MOTOR = -X_END                         # motor pulley in the -x end frame's plane
SADDLE_T = 7.0                           # saddle cheeks and web around each top end bar
SADDLE_WEB = (Z_BAR[0] - 6.0, Z_BAR[0])  # 254..260: web under the bar
Z_PULLEY = SADDLE_WEB[0] - 1.0 - R_FLANGE   # 226: flanges 1 mm under the saddles' webs
IDLER_TRAVEL = (262.0, 282.0)            # idler axle x range (belt tension)
X_IDLER = 272.0                          # nominal: the drawings and the belt length use it
Z_RUN_LAND = Z_PULLEY + R_TIP            # 254.30: upper run's tooth-side face (teeth hang below)
Z_RUN_BACK = Z_PULLEY + R_BELT_BACK      # 256.04: upper run's back
Z_RUN_TIPS = Z_RUN_LAND - BELT["tooth_h"]
Z_LOW_LAND = Z_PULLEY - R_TIP            # 207.70: lower run (teeth up)
C_NOM = X_IDLER - X_MOTOR
BELT_LOOP = 2 * C_NOM + math.pi * PD     # closed-loop length at the nominal idler position
BELT_LOOP_RANGE = tuple(2 * (x - X_MOTOR) + math.pi * PD for x in IDLER_TRAVEL)
CLAMP_BITE = 30.0                        # belt length each open end has in the clamp
BELT_OPEN_CUT = BELT_LOOP + 2 * CLAMP_BITE - 70.0 + 20.0   # open belt: loop + both bites - clamp + spare

# motor mount: the motor's face on a plate at y 11..18, body behind it (+y), shaft forward
MOTOR_PLATE_Y = (PULLEY_W / 2 + 1.0, PULLEY_W / 2 + 8.0)
Y_MOTOR_FACE = MOTOR_PLATE_Y[1]

# idler mount: cheeks either side of the pulley with windows for the axle sliders
AXLE_D = 5.0                             # M5 bolt; 4.0 for an M4
CHEEK_T = 6.0
CHEEK_Y = (PULLEY_W / 2 + 0.5, PULLEY_W / 2 + 0.5 + CHEEK_T)   # 10.5..16.5
SLIDER = dict(x=12.0, z=22.0, axle_dz=-4.0, screw_dz=6.0)       # axle 4 below, screw 6 above its centre
TENSION_SCREW = "M3"

# ---------------------------------------------------------------- carriage: belt clamp
CLAMP = dict(len=70.0, col_x=40.0, col_y=24.0, wall=3.0, chan=8.0, side=18.0, jaw_base=5.0,
             flange=(60.0, 32.0, 6.0), screw_x=26.0, screw_y=13.0)

# ---------------------------------------------------------------- pivot, pendulum, sensor
ARM_GAP = 8.0                            # arm to the frame's front face
ARM_T, ARM_W = 10.0, 20.0                # arm section: thickness along y, width along x
Y_ARM = Y_FRONT - ARM_GAP - ARM_T / 2    # -153
HUB = dict(len=18.0, r=15.0, socket=25.0)
Y_HUB = (Y_ARM - HUB["len"] / 2, Y_ARM + HUB["len"] / 2)   # -162..-144
KP08 = dict(l=55.0, j=42.0, a=13.0, base_t=5.5, h=15.0, top=28.5, ring_w=19.0, ring_od=15.0, slot=6.5)
Y_KP_F = Y_HUB[1] + 1.5 + KP08["ring_w"] / 2        # -134: front pillow block
KP_SPACING = 70.0
Y_KP_R = Y_KP_F + KP_SPACING                        # -64: rear pillow block
BRIDGE_T = 12.0
BRIDGE_X = 32.0                                     # half-width of the pivot bridge
Z_BRIDGE1 = Z_PLATE1 + BRIDGE_T                     # 351
Z_SHAFT = Z_BRIDGE1 + KP08["h"]                     # 366: pivot axis
SHAFT_D = 8.0
TOWER_T = 5.0
Y_TOWER = Y_KP_R + 33.0                             # -31: sensor tower's front face
Y_BRIDGE = (Y_KP_F - KP08["a"] / 2 - 1.5, Y_TOWER + TOWER_T)   # -142..-26
BRIDGE_SLIDE = 10.0                                 # the bridge slides +-10 in y: frames 260..300 wide fit
Y_SHAFT_END = Y_TOWER - 14.5                        # -45.5
SHAFT_L = 115.0
Y_SHAFT_START = Y_SHAFT_END - SHAFT_L               # -160.5
ARM_L = 300.0                                       # pivot axis to the arm's tip
TIP = dict(len=24.0, wall=2.4)                      # tip cap over the arm's end
AS5600 = dict(board=23.0, pcb=1.6, chip=1.5, standoff=6.0, magnet_d=6.0, magnet_t=2.5, gap=1.5)   # adapter 3 + pads 3
Y_MAGNET = Y_TOWER - AS5600["standoff"] - AS5600["pcb"] - AS5600["chip"] - AS5600["gap"]   # magnet face
CAP = dict(y0=Y_SHAFT_END - 8.0, y1=Y_MAGNET, r=9.0)                # magnet cap on the shaft end
LPD3806 = dict(d=38.0, length=35.5, shaft=6.0, shaft_len=13.0, boss_d=20.0, boss_h=5.0, pcd=(28.0, 32.0))
COUPLER = dict(y0=Y_SHAFT_END - 8.0, y1=Y_TOWER - 1.0, r=9.0)

# ---------------------------------------------------------------- limit switches, cables, electronics
ENDSTOP = dict(pcb=(40.0, 16.0, 1.6), hole_dx=19.0, sw=(12.8, 5.8, 6.5), lever=14.0)
Y_SWITCH = 50.0
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
MOTOR_TORQUE_USE = 0.5                   # fraction of the holding torque relied on at speed
V_MAX = 1.5                              # m/s cart speed limit (stepper ~600 rpm)
STEPS_PER_REV = 200 * 16                 # 1/16 microstepping
MASS_VITAMINS_CART = dict(sc8uu=4 * 0.040, kp08=2 * 0.065, screws=0.040, as5600=0.004)
STEEL = 7.85                             # g/cm^3
