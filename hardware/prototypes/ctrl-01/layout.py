"""CTRL-01 layout: every number the rig shares, in one place.

Device frame (mm), the same frame the owner layout sketch uses:
    X  in from the left side face (the key side), 0..68
    Y  down from the top face, 0..110
    Z  back from the front face, 0..29; the seam is at Z = 14.5

Key frame, per key (right-handed, so a key is placed by a rotation, never a mirror):
    x' = Z - KEY_Z        across the slide lock; the catch is on the +x' face (toward the back)
    y' = Y - key centre   along the row; +y' is toward the spring housing (down)
    z' = KEY_BOTTOM - X   along the press, outward; the cap is at the top

Shrunk 26 Oct (Michael): the LADDER-style one-piece key, scaled to the device row.
Wherever a number came from LADDER-01/02 or FIT-01 it says so.
"""

from __future__ import annotations

import math

# --- shell --------------------------------------------------------------------
W, H, T = 68.0, 110.0, 29.0
WALL = 2.5
SEAM = 14.5
CORNER_R = 9.0               # plan corners (WM-F5-style chunky)
EDGE_CH = 1.0                # front/back face edge chamfer
TONGUE_W, TONGUE_H = 1.2, 1.4
GROOVE_CLR = 0.10            # tongue in groove, per side; plate 0 was planned to pick this
RIDGE_H = 0.45               # snap ridges on the tongue, 45 degrees both ways (0.25 pulled apart too easily, 31 Oct)
RIDGE_LEN = 10.0

# --- key row (1 Nov: block keys, no caps; Play..Stop side by side, a gap, then Record) ---
PITCH = 13.0
ROW = ("rec", "gap", "play", "ff", "rew", "stop")     # top to bottom (Michael, 26 Oct)
KEY_Y = {"rec": 21.0, "play": 46.0, "ff": 59.0, "rew": 72.0, "stop": 85.0}
KEY_Z = 13.5                                          # key body centre depth (seam at 14.5)


def key_y(name: str) -> float:
    return KEY_Y[name]


KEYS = tuple(n for n in ROW if n != "gap")
FIN_Y = (KEY_Y["rec"] - PITCH / 2, KEY_Y["rec"] + PITCH / 2) + tuple(
    KEY_Y["play"] - PITCH / 2 + PITCH * i for i in range(5))           # 14.5, 27.5, 39.5 .. 91.5

# --- key ----------------------------------------------------------------------
STEM_XP, STEM_YP = 12.0, 7.0        # x' (device depth) and y' (row)
BODY_H = 9.0                        # z': underside to shoulder
RAIL_W, RAIL_P = 2.5, 1.0           # on the +/-y' faces, centred on x' = 0 (LADDER: 3.0, 1.5)
GROOVE_OD, BOSS_D, GROOVE_D = 5.0, 3.0, 2.2   # pencil spring (FIT-01: OD fits 4.5, grips 3.0)
TRAVEL = 4.0                        # 1 Nov (Michael): was 5.0; the block's inner face lands on the comb
# the block: what you see and press. It runs straight out of the shell, no cap.
BLOCK_YP = 12.4                     # along the row; 0.6 mm gaps on the 13 mm pitch
BLOCK_Z = (5.8, 21.8)               # device Z: 16 mm of the side face's 29
BLOCK_PROUD = 4.0                   # stands this far out of the side face at rest
BLOCK_R = 1.0                       # round on the block's edges
FLANGE_T, FLANGE_ZP = 1.0, 0.55     # inside the wall: stops the key at rest. Back edge only;
                                    # the front zone (Record's toe, the latch slider) lives in front
HOLE_CLR = 0.2                      # aperture round the block, per side
KEY_BOTTOM = WALL + FLANGE_T + BODY_H   # X of the key's underside at rest (12.5)
BLOCK_Z0 = BODY_H                   # z' where the block (and the flange) start
BLOCK_TOP = BODY_H + FLANGE_T + WALL + BLOCK_PROUD   # z' of the block's outer face (16.5)
FIN_X0 = KEY_BOTTOM - BODY_H + TRAVEL   # 7.5: the comb's fins start here and stop the block
SLIDE_CLR = 0.15                    # FIT-01: key slide, per side

# --- catch (P business end, run-on root) --------------------------------------
TOOTH_X = 2.2                       # +x' protrusion from the stem face
HOOK = 1.2                          # P (LADDER-01 ranking)
LEDGE = 4.4                         # z' of the flat ledge (5.2 with 5 mm travel); the ramp line runs on to z' = 0
PAWL_EDGE = 0.5                     # pawl's catch edge, +y' of the key centre, bar at rest (LADDER)
REST_GAP = 0.4                      # pawl top below the ramp, in the pawl's lane (1.0 with 5 mm travel)
RECORD_RAISE = 0.0                  # Record's catch height offset. 0: the pawl chamfer already makes
                                    # every key meet the lock at 2.0 mm, past the blocker's 1.2
STOP_SHIFT = 2.1                    # LADDER: bar shift under Stop
STOP_RAMP_DEG = 38.0                # from the press direction (30 with 5 mm travel: 4 mm is too short
                                    # for 30 degrees to shift the lock 2.1 mm)
STOP_FULL_AT = 3.2                  # press depth where Stop's shift is complete (4.0 with 5 mm travel)

# --- slide lock (bar) and pawls -------------------------------------------------
PAWL_TOP = LEDGE - HOOK - REST_GAP  # z' of the pawl top at rest (3.0)
PAWL_H = 1.6                        # catch region height; the back region runs on to the bar
PAWL_LEN = 5.5                      # y'; 3.9 on the 11 mm pitch. The 13 mm pitch lets it run on toward LADDER's 7
PAWL_CH = 1.0                       # 45 degree chamfer on the corner the ramps meet (LADDER)
PAWL_RISE = 1.7                     # LADDER rev-3 Stop latch: the top rises this much toward the
                                    # far end (Michael, 28 Oct: every latch gets the Stop shape)
PAWL_XP = (7.0, 9.4)                # x' extent: overlaps the catch (6.0..8.2) by 1.2
BAR_X = (KEY_BOTTOM - 5.4, KEY_BOTTOM + 0.4)   # 7.1 .. 12.9; 5.8 wide (31 Oct: 0.1 off each side)
BAR_Z = (KEY_Z + PAWL_XP[1], T - WALL - 0.15)            # 22.9 .. 26.35
BAR_Y0 = FIN_Y[2] - 1.8             # rest: the top end sits on the stop block. Play is the first pawl
BAR_TRAVEL_MAX = 2.8
BAR_SPRING_Z = 24.1
SPRING_REST = 11.0                  # bar spring (pencil, 14 free / 4 solid)
CHANNEL_CLR = 0.15
LIP = 0.35

# --- front zone (the shell's pedestal, ground wall and front guide are sized from these) ---
BLOCK_STOP = 1.2                    # the 27 Oct blocker: kept only for the shell features it sized
FRONT_ZONE = (WALL, KEY_Z - STEM_XP / 2)   # Z 2.5 .. 7.5, in front of the keys
BLOCKER_Z = (2.8, 5.6)
ARM_Z = (5.8, KEY_Z - STEM_XP / 2)
FINGER_Z = (3.0, KEY_Z - STEM_XP / 2)
PIN_SIDE = 1.6                      # square pin turned 45 degrees: its flats ride the 45 degree slot
PIN_Y = key_y("play") - 5.5         # 42.5
PIN_X_REST = 10.2
SLOT_CLR = 0.15

# --- Record latch (31 Oct): Record latches to Play through a slider Play drives -----
# Record no longer has a catch, so it never moves the slide lock and cannot pop Play.
PLAY_HOLD = 3.2                     # Play's latched depth (mech.kinematics("play").latched_at)
LATCH_FLOOR_Z = (2.7, 3.5)          # the slider's floor; Record's toe passes over it
LATCH_TOP = BLOCKER_Z[1]            # 5.6: the hook and the slot walls, under the pedestal
TOE_Z = (3.7, 5.8)                  # Record's toe hangs from its web (WEB_Z)
WEB_Z = (5.8, KEY_Z - STEM_XP / 2 - 0.2)
TOE_X = (KEY_BOTTOM - 1.6, KEY_BOTTOM)                 # 10.9 .. 12.5 at rest
TOE_Y = (key_y("rec") + 7.0, key_y("rec") + 9.0)       # 28 .. 30, under the comb's fin
TOE_CH = 1.0                        # chamfer on the toe's leading inner corner: pushes the hook aside
HOOK_OVERLAP = 0.6                  # hook over the toe's back face, Play latched
HOOK_X = (TOE_X[1] + 0.3, TOE_X[1] + 1.5)              # 12.8 .. 14.0
HOOK_W = 1.0
RAIL_C = (KEY_BOTTOM - 2.7, key_y("play") - 3.0)       # Play's diagonal rail, centre at rest (device X, Y)
SLIDER_X0 = KEY_BOTTOM - 3.3        # the slider's inner edge, riding the front half's guide
GROUND_X = (17.2, 18.7)             # back-half wall the slider's outer edge rides
RAIL_L, RAIL_T = 4.0, 1.6

# --- bay (the sectioned-off transport) -----------------------------------------
SPINE_X = (KEY_BOTTOM + TRAVEL + 2.8, KEY_BOTTOM + TRAVEL + 4.8)   # 19.3 .. 21.3
BAY_Y = (10.0, 107.0)
SPRING_BOSS_L = 2.0
COMB_CLR = 0.15                     # comb to back half, every side (FIT-01 slide clearance)
BACKSTOP_T = 1.2                    # back-half wall behind the spine; takes the key springs

# --- cards and slots ------------------------------------------------------------
CARD = (40.0, 36.0, 7.0)            # GameCube class (owner layout, 24 Oct)
CARD_P_LEN = 42.0                   # 31 Oct portrait cards: 2 mm taller, so 5 mm proud
PROUD = 3.0
POCKET_WALL = 1.2
RAIL_OVER = 1.2
FRONT_CARD_Z = 2.8
BACK_CARD_Z = T - 2.8


def stop_tip_z() -> float:
    """z' where Stop's ramp ends: the pawl's catch edge is fully pushed aside once
    the bottom of its chamfer reaches here, at press depth STOP_FULL_AT."""
    return PAWL_TOP - PAWL_CH + STOP_FULL_AT


def deg_slope(deg: float) -> float:
    """dz per dy for a ramp `deg` from the press direction."""
    return 1 / math.tan(math.radians(deg))
