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
RIDGE_H = 0.25               # snap ridges on the tongue, 45 degrees both ways

# --- key row ------------------------------------------------------------------
PITCH = 11.0
ROW = ("rec", "gap", "play", "ff", "rew", "stop")     # top to bottom (Michael, 26 Oct)
ROW_Y0 = 26.0                                         # Record's centre; keeps caps clear of the bumpers
KEY_Z = 13.5                                          # key centre depth (seam at 14.5)


def key_y(name: str) -> float:
    return ROW_Y0 + PITCH * ROW.index(name)


KEYS = tuple(n for n in ROW if n != "gap")
FIN_Y = tuple(ROW_Y0 - PITCH / 2 + PITCH * i for i in range(len(ROW) + 1))

# --- key ----------------------------------------------------------------------
STEM_XP, STEM_YP = 12.0, 7.0        # x' (device depth) and y' (row)
BODY_H = 9.0                        # z': underside to shoulder
RAIL_W, RAIL_P = 2.5, 1.0           # on the +/-y' faces, centred on x' = 0 (LADDER: 3.0, 1.5)
GROOVE_OD, BOSS_D, GROOVE_D = 5.0, 3.0, 2.2   # pencil spring (FIT-01: OD fits 4.5, grips 3.0)
TRAVEL = 5.0                        # was 6.2 on LADDER; the cap underside lands on the shell
CAP_XP, CAP_YP, CAP_T, CAP_R = 12.0, 8.0, 2.5, 1.5
INSET = 1.25                        # extension inset per side
HOLE_CLR = 0.25                     # aperture round the extension, per side
KEY_BOTTOM = WALL + BODY_H          # X of the key's underside at rest (11.5)
CAP_Z0 = BODY_H + WALL + TRAVEL     # z' of the cap underside (16.5)
SLIDE_CLR = 0.15                    # FIT-01: key slide, per side

# --- catch (P business end, run-on root) --------------------------------------
TOOTH_X = 2.2                       # +x' protrusion from the stem face
HOOK = 1.2                          # P (LADDER-01 ranking)
LEDGE = 5.2                         # z' of the flat ledge; the ramp line runs on to z' = 0 at the face edge
PAWL_EDGE = 0.5                     # pawl's catch edge, +y' of the key centre, bar at rest (LADDER)
REST_GAP = 1.0                      # pawl top below the ramp, measured in the pawl's lane
RECORD_RAISE = 0.0                  # Record's catch height offset. 0: the pawl chamfer already makes
                                    # every key meet the lock at 2.0 mm, past the blocker's 1.2
STOP_SHIFT = 2.1                    # LADDER: bar shift under Stop
STOP_RAMP_DEG = 30.0                # from the press direction
STOP_FULL_AT = 4.0                  # press depth where Stop's shift is complete

# --- slide lock (bar) and pawls -------------------------------------------------
PAWL_TOP = LEDGE - HOOK - REST_GAP  # z' of the pawl top at rest (3.0)
PAWL_H = 1.6                        # catch region height; the back region runs on to the bar
PAWL_LEN = 3.9                      # y'; limited by the next key's catch root at full bar travel
PAWL_CH = 1.0                       # 45 degree chamfer on the corner the ramps meet (LADDER)
PAWL_RISE = 1.7                     # LADDER rev-3 Stop latch: the top rises this much toward the
                                    # far end (Michael, 28 Oct: every latch gets the Stop shape)
PAWL_XP = (7.0, 9.4)                # x' extent: overlaps the catch (6.0..8.2) by 1.2
BAR_X = (6.0, 12.0)
BAR_Z = (KEY_Z + PAWL_XP[1], T - WALL - 0.15)            # 22.9 .. 26.35
BAR_Y0 = FIN_Y[0] - 1.8             # rest: the top end sits on the stop block
BAR_TRAVEL_MAX = 2.8
BAR_SPRING_Z = 24.1
SPRING_REST = 11.0                  # bar spring (pencil, 14 free / 4 solid)
CHANNEL_CLR = 0.15
LIP = 0.35

# --- Record blocker -------------------------------------------------------------
BLOCK_STOP = 1.2                    # Record moves this far, then lands on the blocker, while Play is up
FRONT_ZONE = (WALL, KEY_Z - STEM_XP / 2)   # Z 2.5 .. 7.5, in front of the keys
BLOCKER_Z = (2.8, 5.6)
ARM_Z = (5.8, KEY_Z - STEM_XP / 2)
FINGER_Z = (3.0, KEY_Z - STEM_XP / 2)
PIN_SIDE = 1.6                      # square pin turned 45 degrees: its flats ride the 45 degree slot
PIN_Y = key_y("play") - 5.5         # 42.5
PIN_X_REST = 10.2
SLOT_CLR = 0.15

# --- bay (the sectioned-off transport) -----------------------------------------
SPINE_X = (KEY_BOTTOM + TRAVEL + 2.8, KEY_BOTTOM + TRAVEL + 4.8)   # 19.3 .. 21.3
BAY_Y = (13.5, 105.0)
SPRING_BOSS_L = 2.0

# --- cards and slots ------------------------------------------------------------
CARD = (40.0, 36.0, 7.0)            # GameCube class (owner layout, 24 Oct)
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
