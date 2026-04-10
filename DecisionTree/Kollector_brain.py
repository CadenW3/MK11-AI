"""
kollector_bot_v12.py  —  Block-First Architecture

PHILOSOPHY: Default state is BLOCKING (holding back). The bot only
releases back to attack when it has confirmed a safe window. After
every attack, immediately returns to holding back.

THREAT DETECTION (no AID — uses only reliable signals):
  1. HP DROP: Our HP decreased → we're getting hit → hold block harder
  2. APPROACH VELOCITY: Opponent X closing rapidly → likely attacking
  3. DISTANCE COLLAPSE: Distance dropped significantly in few frames → rushing in
  4. RAW INPUT: Bonus signal when DMA catches it (unreliable but helpful)
  5. OPPONENT Y: Y > 0 → airborne (jump-in threat or juggle state)

SAFE WINDOW DETECTION (when to attack):
  1. HP stable for 20+ frames (no damage taken recently)
  2. Opponent NOT approaching (velocity near zero or moving away)
  3. Distance is favorable for the chosen move
  4. We are not currently being combo'd (no rapid HP drops)

STRING TIMING: All combo strings use HIT_GAP=12 frames between inputs.
Button holds are 2-3 frames. Special cancel windows are 4 frames after
the last string hit.
"""

import time
import numpy as np
import vgamepad as vg
from collections import deque
from DMA import VisionEngine

# ═══════════════════════════════════════════════════════════════════════
# GAMEPAD CONSTANTS
# ═══════════════════════════════════════════════════════════════════════
gamepad = vg.VX360Gamepad()
FRAME = 1.0 / 60.0

BTN   = vg.XUSB_BUTTON
UP    = BTN.XUSB_GAMEPAD_DPAD_UP
DOWN  = BTN.XUSB_GAMEPAD_DPAD_DOWN
LEFT  = BTN.XUSB_GAMEPAD_DPAD_LEFT
RIGHT = BTN.XUSB_GAMEPAD_DPAD_RIGHT
B1    = BTN.XUSB_GAMEPAD_X       # Square / 1 / FP
B2    = BTN.XUSB_GAMEPAD_Y       # Triangle / 2 / BP
B3    = BTN.XUSB_GAMEPAD_A       # Cross / 3 / FK
B4    = BTN.XUSB_GAMEPAD_B       # Circle / 4 / BK
LB    = BTN.XUSB_GAMEPAD_LEFT_SHOULDER   # Block / L1
RB    = BTN.XUSB_GAMEPAD_RIGHT_SHOULDER  # Amp / R1

# ═══════════════════════════════════════════════════════════════════════
# OPPONENT INPUT BITMASK (from raw gamepad read — unreliable)
# ═══════════════════════════════════════════════════════════════════════
INP_UP   = 1
INP_DOWN = 2
INP_LEFT = 4
INP_RGT  = 8
INP_FP   = 64     # 1 / Square
INP_BP   = 16     # 2 / Triangle
INP_FK   = 32     # 3 / Cross
INP_BK   = 128    # 4 / Circle
INP_THRW = 4096
INP_ATK  = INP_FP | INP_BP | INP_FK | INP_BK

def inp_any_attack(m):  return bool(m & INP_ATK)
def inp_low_atk(m):     return bool(m & INP_DOWN) and bool(m & INP_ATK)
def inp_jump_atk(m):    return bool(m & INP_UP) and bool(m & INP_ATK)
def inp_throw(m):       return bool(m & INP_THRW)
def inp_jumping(m):     return bool(m & INP_UP) and not bool(m & INP_ATK)
def inp_crouching(m):   return bool(m & INP_DOWN) and not bool(m & INP_ATK)


# ═══════════════════════════════════════════════════════════════════════
# GAMEPAD PRIMITIVES
# ═══════════════════════════════════════════════════════════════════════

def _press(btns, hold=2, gap=0):
    """Press buttons for `hold` frames, release, wait `gap` frames."""
    gamepad.reset()
    for b in btns:
        if b:
            gamepad.press_button(b)
    gamepad.update()
    time.sleep(FRAME * max(1, hold))
    gamepad.reset()
    gamepad.update()
    if gap > 0:
        time.sleep(FRAME * gap)


def _hold_back(bwd, low=False):
    """Hold back direction to block. This IS the default stance."""
    gamepad.reset()
    if low:
        gamepad.press_button(DOWN)
    gamepad.press_button(bwd)
    gamepad.update()


def _hold_crouch_block(bwd):
    """Hold down+back for crouching block."""
    gamepad.reset()
    gamepad.press_button(DOWN)
    gamepad.press_button(bwd)
    gamepad.update()


def _release():
    """Release all buttons — only used momentarily before attack inputs."""
    gamepad.reset()
    gamepad.update()


def _motion(dirs, btn, gap=0):
    """Execute a motion input (e.g. QCB, QCF, etc)."""
    for d in dirs:
        gamepad.reset()
        if d:
            gamepad.press_button(d)
        gamepad.update()
        time.sleep(FRAME * 2)
    gamepad.reset()
    if btn:
        gamepad.press_button(btn)
    gamepad.update()
    time.sleep(FRAME * 2)
    gamepad.reset()
    gamepad.update()
    if gap > 0:
        time.sleep(FRAME * gap)


# ═══════════════════════════════════════════════════════════════════════
# MOVE EXECUTOR — executes single moves by notation
# ═══════════════════════════════════════════════════════════════════════

def do(key, fwd, bwd, gap=0):
    """Execute a single move by MK notation."""
    match key:
        # ── Basic Attacks (Normals) ──
        case "1":      _press([B1], 2, gap)           # Claw Swipe — High, 8f startup
        case "2":      _press([B2], 2, gap)           # Lantern Burst — Mid, 12f
        case "3":      _press([B3], 2, gap)           # Violent Heel — Mid, 11f
        case "4":      _press([B4], 2, gap)           # Malice Mace — High, 13f, long range
        # ── Forward Normals ──
        case "F1":     _press([fwd, B1], 2, gap)      # Sickle Slice — Low, 15f
        case "F2":     _press([fwd, B2], 2, gap)      # Knee Breaker — Overhead, 23f
        case "F3":     _press([fwd, B3], 2, gap)      # Korrupted Kick — Mid, 16f, gap closer
        case "F4":     _press([fwd, B4], 2, gap)      # Mace Drop — Overhead, 26f
        # ── Back Normals ──
        case "B1":     _press([bwd, B1], 2, gap)      # Raising Hell — Mid, 15f
        case "B2":     _press([bwd, B2], 2, gap)      # Lantern Slam — Mid, 10f, stagger
        case "B3":     _press([bwd, B3], 2, gap)      # Death Spin — Mid, 14f
        case "B4":     _press([bwd, B4], 2, gap)      # Tax Burden — Mid, 16f
        # ── Down Normals (Pokes) ──
        case "D1":     _press([DOWN, B1], 2, gap)     # Bloody Nails — Mid, 8f, fastest poke
        case "D2":     _press([DOWN, B2], 2, gap)     # Rising Claws — Mid, 7f, BEST anti-air
        case "D3":     _press([DOWN, B3], 2, gap)     # Leg Check — Low, 11f
        case "D4":     _press([DOWN, B4], 2, gap)     # Low Mace — Low, 14f
        # ── Special Moves ──
        case "DB3":    _motion([DOWN, bwd], B3, gap)   # Shotel Fury — Mid, 11f
        case "DB3A":                                    # Amplified Shotel Fury
            _motion([DOWN, bwd], B3, 0)
            time.sleep(FRAME * 2)
            _press([RB], 2, gap)
        case "DBF3":   _motion([DOWN, bwd, fwd], B3, gap)  # Demonic Clutch — command grab
        case "DF1":    _motion([DOWN, fwd], B1, gap)   # Bag Bomb — projectile
        case "DF1F":                                    # Far Bag Bomb
            _motion([DOWN, fwd], B1, 0)
            _press([fwd], 2, gap)
        case "BF2":    _motion([bwd, fwd], B2, gap)    # Demonic Mace — ranged, chargeable
        case "BF4":    _motion([bwd, fwd], B4, gap)    # Damned Bola / War-Quoit Toss
        case "BF4A":                                    # Amplified Bola
            _motion([bwd, fwd], B4, 0)
            time.sleep(FRAME * 2)
            _press([RB], 2, gap)
        case "DB4":    _motion([DOWN, bwd], B4, gap)   # Relic Absorb / Relic Lure
        case "DB4A":                                    # Amplified Relic
            _motion([DOWN, bwd], B4, 0)
            time.sleep(FRAME * 2)
            _press([RB], 2, gap)
        case "DB1":    _motion([DOWN, bwd], B1, gap)   # Vial of Sorrow — DoT zone
        case "DB1B":                                    # Close Vial
            _motion([DOWN, bwd], B1, 0)
            _press([bwd], 2, gap)
        case "DB1F":                                    # Far Vial
            _motion([DOWN, bwd], B1, 0)
            _press([fwd], 2, gap)
        case "DB2":    _motion([DOWN, bwd], B2, gap)   # Up Demonic Mace — anti-air special
        # ── Teleport ──
        case "DD3":                                     # Fade Out — teleport behind opponent
            _press([DOWN], 2, 1)
            _press([DOWN, B3], 2, gap)
        case "DD3F":                                    # Far Fade Out — teleport away
            _press([DOWN], 2, 1)
            _press([DOWN, B3], 2, 0)
            _press([fwd], 2, gap)
        # ── Throws ──
        case "THROW_F": _press([fwd, B1, B3], 2, gap)  # Forward throw
        case "THROW_B": _press([bwd, B1, B3], 2, gap)  # Back throw
        # ── Hop Attacks ──
        case "HOP12":  _press([UP, B1], 3, gap)        # Menacing Fist (hop 1 or 2)
        case "HOP2":   _press([UP, B2], 3, gap)        # Hop Triangle — key juggle tool
        case "HOP34":  _press([UP, B3], 3, gap)        # Debt Kick (hop 3 or 4)
        # ── Fatal Blow ──
        case "FATAL":  _press([LB, RB], 3, gap)        # A SLIGHT DONATION
        # ── Getup/Flawless Block attacks ──
        case "GETUP2": _press([UP, B2], 3, gap)        # Flailing Mace — getup attack
        case "GETUP3": _press([UP, B3], 3, gap)        # Rising Flames — getup attack
        case _:
            pass


# ═══════════════════════════════════════════════════════════════════════
# KOMBO STRINGS — with proper inter-hit timing
#
# MK11 requires ~10-14 frames between string inputs for the game to
# register each hit in sequence. Without this gap, the game eats the
# inputs and does a special cancel or nothing.
# ═══════════════════════════════════════════════════════════════════════

HIT_GAP = 12   # frames between string hits
CANCEL_GAP = 4 # frames before special cancel after last string hit


def string_13(f, b):
    """1,3 — Claw Swipe → Violent Heel. 8f startup. Main punish starter.
    Hit properties: High, Mid. On block: -6."""
    _press([B1], 2, HIT_GAP)
    _press([B3], 2, CANCEL_GAP)


def string_f12(f, b):
    """F1,2 — Sickle Slice → Lantern Burst. Low starter.
    Hit properties: Low, Mid. On block: -7."""
    _press([f, B1], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)


def string_b12(f, b):
    """B1,2 — Raising Hell → Lantern Burst. Mid string.
    Hit properties: Mid, Mid. On block: -4."""
    _press([b, B1], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)


def string_443(f, b):
    """4,4,3 — Ravages of Time. LAUNCHER on hit.
    Hit properties: High, High, Mid. On block: -14 (very unsafe).
    On hit: launches for full combo."""
    _press([B4], 2, HIT_GAP)
    _press([B4], 2, HIT_GAP)
    _press([B3], 2, CANCEL_GAP)


def string_b34(f, b):
    """B3,4 — Death Spin → Malice Mace.
    Hit properties: Mid, High. On block: -6."""
    _press([b, B3], 2, HIT_GAP)
    _press([B4], 2, CANCEL_GAP)


def string_b43(f, b):
    """B4,3 — Tax Burden → Violent Heel.
    Hit properties: Mid, Mid. On block: -8."""
    _press([b, B4], 2, HIT_GAP)
    _press([B3], 2, CANCEL_GAP)


def string_f44(f, b):
    """F4,4 — Mace Drop → Malice Mace.
    Hit properties: Overhead, High. On block: -3 (safe)."""
    _press([f, B4], 2, HIT_GAP)
    _press([B4], 2, CANCEL_GAP)


def string_212(f, b):
    """2,1,2 — Lantern Burst → Claw Swipe → Lantern Burst.
    Hit properties: Mid, High, Mid. On block: -7."""
    _press([B2], 2, HIT_GAP)
    _press([B1], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)


def string_f12_full(f, b):
    """F1,2,1+3 — Sickle Slice → Lantern → Throw ender (Taxed kombo).
    Hit properties: Low, Mid, Throw. On hit: hard knockdown."""
    _press([f, B1], 2, HIT_GAP)
    _press([B2], 2, HIT_GAP)
    _press([B1, B3], 2, CANCEL_GAP)


# ═══════════════════════════════════════════════════════════════════════
# AERIAL JUGGLE ENDERS
#
# After a launcher (4,4,3 / D2 KB), the opponent is airborne. These
# enders pick them up mid-air and slam them down.
# ═══════════════════════════════════════════════════════════════════════

def juggle_hop2_db3(f, b):
    """Standard aerial ender: hop triangle → Shotel Fury."""
    _press([UP, B2], 3, 0)       # hop triangle — hits opponent mid-air
    time.sleep(FRAME * 6)         # hop arc duration
    _motion([DOWN, b], B3, 0)     # DB3 Shotel Fury as we land


def juggle_hop2_dbf3(f, b):
    """Kill ender: hop triangle → Demonic Clutch (max damage)."""
    _press([UP, B2], 3, 0)
    time.sleep(FRAME * 6)
    _motion([DOWN, b, f], B3, 0)  # DBF3 Demonic Clutch


def juggle_hop2_db3a(f, b):
    """Amp ender: hop triangle → Amplified Shotel Fury (extra hits)."""
    _press([UP, B2], 3, 0)
    time.sleep(FRAME * 6)
    _motion([DOWN, b], B3, 0)     # DB3
    time.sleep(FRAME * 2)
    _press([RB], 2, 0)            # Amplify


def juggle_hop2_bf4a(f, b):
    """Corner carry ender: hop triangle → Amplified Bola."""
    _press([UP, B2], 3, 0)
    time.sleep(FRAME * 6)
    _motion([b, f], B4, 0)        # BF4
    time.sleep(FRAME * 2)
    _press([RB], 2, 0)            # Amplify


def juggle_extended(f, b):
    """Extended juggle: hop triangle → B2 reconnect → DB3.
    More damage but tighter timing. Use after high launchers."""
    _press([UP, B2], 3, 0)        # hop triangle
    time.sleep(FRAME * 5)
    _press([b, B2], 2, 0)         # B2 reconnect while still airborne
    time.sleep(FRAME * 4)
    _motion([DOWN, b], B3, 0)     # DB3 ender


# ═══════════════════════════════════════════════════════════════════════
# FULL COMBO ROUTES
#
# Each combo route is a launcher/starter → string filler → aerial ender.
# The bot selects the appropriate route based on distance, HP, and
# what move started the combo.
# ═══════════════════════════════════════════════════════════════════════

def combo_ravages_standard(f, b):
    """4,4,3 → hop2 → DB3. Bread and butter. ~28% damage."""
    string_443(f, b)
    juggle_hop2_db3(f, b)


def combo_ravages_kill(f, b):
    """4,4,3 → hop2 → DBF3 Clutch. Kill confirm. ~33% damage."""
    string_443(f, b)
    juggle_hop2_dbf3(f, b)


def combo_ravages_amp(f, b):
    """4,4,3 → hop2 → Amp DB3. Mid-damage, safe. ~31% damage."""
    string_443(f, b)
    juggle_hop2_db3a(f, b)


def combo_ravages_extended(f, b):
    """4,4,3 → hop2 → B2 → DB3. Max damage route. ~35% damage."""
    string_443(f, b)
    juggle_extended(f, b)


def combo_f12_juggle(f, b):
    """F1,2 (low) → hop2 → DB3. Low starter into full combo."""
    string_f12(f, b)
    juggle_hop2_db3(f, b)


def combo_f12_kill(f, b):
    """F1,2 (low) → hop2 → Clutch. Low starter kill confirm."""
    string_f12(f, b)
    juggle_hop2_dbf3(f, b)


def combo_f2_overhead(f, b):
    """F2 (overhead) → hop2 → DB3. Overhead starter."""
    _press([f, B2], 2, CANCEL_GAP)
    juggle_hop2_db3(f, b)


def combo_f2_overhead_kill(f, b):
    """F2 (overhead) → hop2 → Clutch. Overhead kill confirm."""
    _press([f, B2], 2, CANCEL_GAP)
    juggle_hop2_dbf3(f, b)


def combo_d2_antiair(f, b):
    """D2 anti-air → hop2 → Amp DB3. Best D2 in the game.
    Krushing Blow if it counters/punishes a high attack."""
    _press([DOWN, B2], 2, CANCEL_GAP)
    juggle_hop2_db3a(f, b)


def combo_d2_antiair_extended(f, b):
    """D2 anti-air → extended juggle. Max damage AA."""
    _press([DOWN, B2], 2, CANCEL_GAP)
    juggle_extended(f, b)


def combo_b12_shotel(f, b):
    """B1,2 → DB3 Shotel Fury. Safe string into special."""
    string_b12(f, b)
    _motion([DOWN, b], B3, 0)


def combo_b12_amp_shotel(f, b):
    """B1,2 → Amp DB3. More damage."""
    string_b12(f, b)
    _motion([DOWN, b], B3, 0)
    time.sleep(FRAME * 2)
    _press([RB], 2, 0)


def combo_13_shotel(f, b):
    """1,3 → DB3. Fastest punish starter into special (8f)."""
    string_13(f, b)
    _motion([DOWN, b], B3, 0)


def combo_13_amp_shotel(f, b):
    """1,3 → Amp DB3. Fast punish with extra damage."""
    string_13(f, b)
    _motion([DOWN, b], B3, 0)
    time.sleep(FRAME * 2)
    _press([RB], 2, 0)


def combo_b34_bola(f, b):
    """B3,4 → BF4 Bola. Mid string into projectile knockdown."""
    string_b34(f, b)
    _motion([b, f], B4, 0)


def combo_b34_amp_bola(f, b):
    """B3,4 → Amp BF4. Corner carry."""
    string_b34(f, b)
    _motion([b, f], B4, 0)
    time.sleep(FRAME * 2)
    _press([RB], 2, 0)


def combo_212_shotel(f, b):
    """2,1,2 → DB3. Triple hit string into special."""
    string_212(f, b)
    _motion([DOWN, b], B3, 0)


def combo_f44_shotel(f, b):
    """F4,4 → DB3. Overhead starter string (safe on block)."""
    string_f44(f, b)
    _motion([DOWN, b], B3, 0)


def combo_b43_clutch(f, b):
    """B4,3 → DBF3 Clutch. String into command grab."""
    string_b43(f, b)
    _motion([DOWN, b, f], B3, 0)


def combo_f12_throw(f, b):
    """F1,2,1+3 — Full Taxed kombo with throw ender."""
    string_f12_full(f, b)


# ═══════════════════════════════════════════════════════════════════════
# COOLDOWNS (in bot-loop frames, not game frames)
#
# These determine how long the bot waits after executing a move before
# it can act again. Shorter = more aggressive but less safe.
# The bot holds BACK during cooldown, so it's blocking while waiting.
# ═══════════════════════════════════════════════════════════════════════

COOLDOWN = {
    # ── Combo routes ──
    "ravages":          16,
    "ravages_kill":     20,
    "ravages_amp":      18,
    "ravages_ext":      20,
    "f12_juggle":       14,
    "f12_kill":         18,
    "f2_oh":            14,
    "f2_oh_kill":       18,
    "d2_aa":            12,
    "d2_aa_ext":        16,
    "b12_shotel":       12,
    "b12_amp":          14,
    "13_shotel":        10,
    "13_amp":           12,
    "b34_bola":         14,
    "b34_amp":          16,
    "212_shotel":       12,
    "f44_shotel":       14,
    "b43_clutch":       12,
    "f12_throw":        14,
    # ── Single pokes ──
    "d1":                3,
    "d2":                5,
    "d3":                3,
    "d4":                3,
    "1":                 3,
    "2":                 4,
    "3":                 3,
    "4":                 4,
    # ── Directional normals ──
    "f1":                4,
    "f2":                5,
    "f3":                4,
    "f4":                5,
    "b1":                4,
    "b2":                3,
    "b3":                5,
    "b4":                5,
    # ── Specials (standalone, not from strings) ──
    "shotel":            8,
    "amp_shotel":       10,
    "clutch":            8,
    "bagbomb":           8,
    "far_bagbomb":      10,
    "mace":             10,
    "bola":              8,
    "amp_bola":         10,
    "vial":              8,
    "relic":             8,
    "up_mace":          10,
    # ── Movement / Utility ──
    "teleport":          8,
    "far_teleport":     10,
    "throw":             6,
    "fatal":            12,
    "dash":              2,
    "hop_atk":           8,
    "getup":             8,
}


# ═══════════════════════════════════════════════════════════════════════
# THREAT DETECTOR
#
# Multi-signal system that determines threat level using ONLY reliable
# data: HP deltas, position/velocity, distance changes, and raw input
# (when available). No dependency on action_id.
# ═══════════════════════════════════════════════════════════════════════

class ThreatDetector:
    """Tracks opponent behavior and determines if they're threatening us.

    Signals used:
      1. Our HP dropping = confirmed we're being hit
      2. Opponent X velocity toward us = approaching/attacking
      3. Distance closing rapidly = rush/dash/advancing attack
      4. Raw gamepad input (unreliable but used when available)
      5. Opponent Y position = airborne detection
      6. Our HP delta rate = are we being combo'd (rapid successive drops)
    """

    HISTORY_LEN = 30  # frames of history to keep

    def __init__(self):
        # ── Our data ──
        self.our_hp       = deque([1.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self.our_x        = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)

        # ── Opponent data ──
        self.opp_x        = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self.opp_y        = deque([0.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self.opp_hp       = deque([1.0] * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)
        self.opp_inputs   = deque([0]   * self.HISTORY_LEN, maxlen=self.HISTORY_LEN)

        # ── Derived tracking ──
        self.frames_since_our_dmg   = 999  # frames since we last took damage
        self.frames_since_opp_dmg   = 999  # frames since opponent took damage
        self.last_our_hp            = 1.0
        self.last_opp_hp            = 1.0
        self.consecutive_dmg_frames = 0    # how many frames in a row we've taken damage
        self.total_dmg_events       = 0    # count of distinct damage events this round

        # ── Approach tracking ──
        self.opp_approach_frames    = 0    # consecutive frames opponent is approaching
        self.opp_retreat_frames     = 0    # consecutive frames opponent is retreating

    def update(self, p1, p2):
        """Call every frame with fresh game state."""
        self.our_hp.append(p1['hp'])
        self.our_x.append(p1['x'])
        self.opp_x.append(p2['x'])
        self.opp_y.append(p2['y'])
        self.opp_hp.append(p2['hp'])
        self.opp_inputs.append(p2.get('inputs', 0))

        # ── Did we take damage this frame? ──
        cur_hp = p1['hp']
        if cur_hp < self.last_our_hp - 0.002:
            self.frames_since_our_dmg = 0
            self.consecutive_dmg_frames += 1
            self.total_dmg_events += 1
        else:
            if self.frames_since_our_dmg < 999:
                self.frames_since_our_dmg += 1
            if self.frames_since_our_dmg > 4:
                self.consecutive_dmg_frames = 0
        self.last_our_hp = cur_hp

        # ── Did opponent take damage? ──
        opp_hp = p2['hp']
        if opp_hp < self.last_opp_hp - 0.002:
            self.frames_since_opp_dmg = 0
        else:
            if self.frames_since_opp_dmg < 999:
                self.frames_since_opp_dmg += 1
        self.last_opp_hp = opp_hp

        # ── Approach / retreat tracking ──
        if len(self.opp_x) >= 4:
            ox = list(self.opp_x)
            ux = list(self.our_x)
            # Is opponent getting closer to us?
            old_dist = abs(ox[-4] - ux[-4])
            new_dist = abs(ox[-1] - ux[-1])
            delta = old_dist - new_dist  # positive = closing

            if delta > 3.0:  # closing at >1 unit/frame average
                self.opp_approach_frames += 1
                self.opp_retreat_frames = 0
            elif delta < -2.0:  # opening
                self.opp_retreat_frames += 1
                self.opp_approach_frames = 0
            else:
                # Neutral — decay slowly
                self.opp_approach_frames = max(0, self.opp_approach_frames - 1)
                self.opp_retreat_frames = max(0, self.opp_retreat_frames - 1)

    # ── Query methods ──

    def we_took_damage_recently(self, frames=6):
        """True if our HP dropped within the last N frames."""
        return self.frames_since_our_dmg <= frames

    def we_are_being_combod(self):
        """True if we've taken damage multiple times in rapid succession.
        Indicates we're stuck in opponent's combo and need to hold block."""
        return self.consecutive_dmg_frames >= 2

    def our_hp_is_stable(self, frames=20):
        """True if our HP hasn't changed for N+ frames."""
        return self.frames_since_our_dmg >= frames

    def opponent_approaching(self):
        """True if opponent has been closing distance for 3+ frames."""
        return self.opp_approach_frames >= 3

    def opponent_rushing(self):
        """True if opponent is closing distance very aggressively (dash/run)."""
        if len(self.opp_x) < 4:
            return False
        ox = list(self.opp_x)
        ux = list(self.our_x)
        old_dist = abs(ox[-4] - ux[-4])
        new_dist = abs(ox[-1] - ux[-1])
        closing_speed = old_dist - new_dist
        return closing_speed > 12.0  # very fast approach

    def opponent_airborne(self):
        """True if opponent's Y position indicates they're in the air."""
        return max(list(self.opp_y)[-4:]) > 20.0

    def opponent_grounded_approaching(self):
        """True if opponent is approaching on the ground (not jumping)."""
        return self.opponent_approaching() and not self.opponent_airborne()

    def opponent_retreating(self):
        """True if opponent is moving away from us."""
        return self.opp_retreat_frames >= 3

    def raw_input_attack(self):
        """True if raw gamepad shows attack button in last 3 frames."""
        return any(inp_any_attack(m) for m in list(self.opp_inputs)[-3:])

    def raw_input_low(self):
        """True if raw gamepad shows DOWN+attack."""
        return any(inp_low_atk(m) for m in list(self.opp_inputs)[-3:])

    def raw_input_throw(self):
        return any(inp_throw(m) for m in list(self.opp_inputs)[-3:])

    def raw_input_jump(self):
        return any(inp_jumping(m) for m in list(self.opp_inputs)[-4:])

    def opponent_hp_dropping(self):
        """True if opponent took damage recently (our attack landed)."""
        return self.frames_since_opp_dmg <= 6

    def get_current_dist(self):
        """Current distance between players."""
        return abs(list(self.opp_x)[-1] - list(self.our_x)[-1])

    def is_safe_to_attack(self):
        """Returns True when we have a confirmed safe window to attack.

        Safe = we haven't taken damage recently AND opponent is not
        currently rushing toward us AND we're not being combo'd.

        This is the GATE that prevents the bot from attacking into
        an opponent's offense.
        """
        if self.we_took_damage_recently(frames=8):
            return False
        if self.we_are_being_combod():
            return False
        if self.opponent_rushing():
            return False
        return True

    def should_block(self, dist):
        """Returns (should_block: bool, is_low: bool, reason: str).

        This is the primary defensive decision. Uses all signals.
        """
        # ── Signal 1: We just took damage → DEFINITELY block ──
        if self.we_took_damage_recently(frames=6):
            low = self.raw_input_low()
            return True, low, "damage"

        # ── Signal 2: We're being combo'd → hold block ──
        if self.we_are_being_combod():
            low = self.raw_input_low()
            return True, low, "combo"

        # ── Signal 3: Opponent rushing toward us at close range ──
        if self.opponent_rushing() and dist < 450:
            low = self.raw_input_low()
            return True, low, "rush"

        # ── Signal 4: Opponent approaching and in range ──
        if self.opponent_grounded_approaching() and dist < 350:
            low = self.raw_input_low()
            return True, low, "approach"

        # ── Signal 5: Raw input detected (unreliable but use it) ──
        if self.raw_input_attack() and dist < 400:
            low = self.raw_input_low()
            return True, low, "input"

        # ── Signal 6: Raw throw input ──
        if self.raw_input_throw() and dist < 180:
            return False, False, "throw_tech"  # special handling

        return False, False, ""

    def reset(self):
        """Reset between rounds."""
        self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# MIXUP TRACKER
#
# Tracks what offensive options the bot has used recently to stay
# unpredictable. Shifts weights away from overused options.
# ═══════════════════════════════════════════════════════════════════════

class MixupTracker:
    """Tracks low/overhead/throw/grab usage and decays over time."""

    def __init__(self):
        self.low_count    = 0
        self.oh_count     = 0
        self.throw_count  = 0
        self.grab_count   = 0
        self.tick_counter = 0

    def tick(self):
        self.tick_counter += 1
        if self.tick_counter % 40 == 0:
            self.low_count    = max(0, self.low_count - 1)
            self.oh_count     = max(0, self.oh_count - 1)
            self.throw_count  = max(0, self.throw_count - 1)
            self.grab_count   = max(0, self.grab_count - 1)

    def used_low(self):    self.low_count += 1
    def used_oh(self):     self.oh_count += 1
    def used_throw(self):  self.throw_count += 1
    def used_grab(self):   self.grab_count += 1

    def should_force_oh(self):     return self.low_count >= 2
    def should_force_low(self):    return self.oh_count >= 2
    def should_force_grab(self):   return (self.low_count + self.oh_count) >= 3 and self.grab_count < 2
    def should_force_throw(self):  return (self.low_count + self.oh_count) >= 3 and self.throw_count < 2

    def low_weight(self):   return max(0.04, 0.16 - self.low_count * 0.04)
    def oh_weight(self):    return max(0.04, 0.14 - self.oh_count * 0.04)

    def reset(self):
        self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# KOLLECTOR BOT v12 — BLOCK-FIRST ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════

class KollectorBot:
    """Block-first Kollector bot.

    Architecture:
      1. DEFAULT = hold back (block)
      2. Every frame, check if we should BLOCK harder (crouch block,
         react to specific threats)
      3. Only ATTACK when ThreatDetector confirms a safe window
      4. After every attack, immediately return to holding back
      5. Cooldown frames are spent holding back (passive block)

    Distance thresholds (game units):
      THROW_DIST  = 120  — throw range
      GRAB_DIST   = 135  — command grab range
      PB_DIST     = 170  — point blank (close normals land)
      MID_DIST    = 355  — mid range (F3, 4, advancing moves)
      FAR_DIST    = 520  — far range (projectiles, teleport)
      FULL_DIST   = 700  — full screen
    """

    THROW_DIST  = 120
    GRAB_DIST   = 135
    PB_DIST     = 170
    MID_DIST    = 355
    FAR_DIST    = 520
    FULL_DIST   = 700

    def __init__(self):
        self.cd          = 0        # cooldown frames remaining
        self.blocking    = False    # are we in committed block stance
        self.block_low   = False    # are we blocking low
        self.block_timer = 0        # frames we've been blocking
        self.fwd         = RIGHT    # forward direction (updated per frame)
        self.bwd         = LEFT     # back direction
        self.fatal_used  = False    # have we used fatal blow this round

        self.threat  = ThreatDetector()
        self.mixup   = MixupTracker()

    def _facing(self, p1, p2):
        """Determine which direction is forward/back based on positions."""
        if p1['x'] < p2['x']:
            self.fwd, self.bwd = RIGHT, LEFT
        else:
            self.fwd, self.bwd = LEFT, RIGHT

    @staticmethod
    def _dist(p1, p2):
        return abs(p1['x'] - p2['x'])

    # ── BLOCKING METHODS ──────────────────────────────────────────────

    def _enter_block(self, low=False, reason=""):
        """Enter committed block stance."""
        self.blocking = True
        self.block_low = low
        self.block_timer = 0
        _hold_back(self.bwd, low=low)
        return f"BLOCK {'LOW' if low else 'HIGH'} [{reason}]"

    def _maintain_block(self, dist):
        """Called every frame while in committed block. Returns action string
        or None if block should release."""
        self.block_timer += 1

        # Update low/high based on new signals
        if self.threat.raw_input_low():
            self.block_low = True
        elif self.threat.raw_input_attack():
            self.block_low = False

        # Keep holding
        _hold_back(self.bwd, low=self.block_low)

        # ── Release conditions ──

        # Too far to need block
        if dist > self.MID_DIST + 120:
            self.blocking = False
            return None

        # Safety cap — don't block forever
        if self.block_timer >= 120:
            self.blocking = False
            return None

        # Release when HP is stable AND not being approached AND blocked long enough
        if (self.block_timer >= 12
                and self.threat.our_hp_is_stable(frames=20)
                and not self.threat.opponent_approaching()
                and not self.threat.raw_input_attack()):
            self.blocking = False
            return None

        # If we're STILL taking damage, reset block timer
        # (our block direction might be wrong, but keep trying)
        if self.threat.we_took_damage_recently(frames=3):
            self.block_timer = 0
            # Try switching high/low
            self.block_low = not self.block_low

        return "HOLDING BLOCK"

    def _default_guard(self):
        """Default stance: hold back. Used during cooldown and idle."""
        _hold_back(self.bwd)

    # ── MAIN DECISION LOOP ────────────────────────────────────────────

    def decide(self, p1, p2):
        """Main decision function. Called every frame.

        Returns a string describing the action taken.
        """
        self._facing(p1, p2)
        self.threat.update(p1, p2)
        self.mixup.tick()

        dist     = self._dist(p1, p2)
        airborne = self.threat.opponent_airborne()

        # ══════════════════════════════════════════════════════════
        # PRIORITY 1: ARE WE IN COMMITTED BLOCK?
        # If yes, maintain it until release conditions are met,
        # then punish.
        # ══════════════════════════════════════════════════════════
        if self.blocking:
            result = self._maintain_block(dist)
            if result is not None:
                return result
            # Block released — punish if in range
            self.cd = 0
            return self._punish_after_block(dist, p2)

        # ══════════════════════════════════════════════════════════
        # PRIORITY 2: SHOULD WE BLOCK?
        # Check all threat signals. If any trigger, enter block.
        # This fires EVEN during cooldown — defense > offense.
        # ══════════════════════════════════════════════════════════
        should, is_low, reason = self.threat.should_block(dist)

        if should:
            # Throw tech — jump instead of block
            if reason == "throw_tech":
                _press([UP], 2)
                self.cd = 3
                return "TECH THROW [jump]"
            return self._enter_block(low=is_low, reason=reason)

        # ══════════════════════════════════════════════════════════
        # PRIORITY 3: COOLDOWN — hold back (passive block)
        # We're recovering from our last move. Hold back to block
        # anything that comes. If a threat appears, Priority 2
        # will catch it next frame.
        # ══════════════════════════════════════════════════════════
        if self.cd > 0:
            self.cd -= 1
            self._default_guard()
            return "GUARDING"

        # ══════════════════════════════════════════════════════════
        # PRIORITY 4: IS IT SAFE TO ATTACK?
        # Only proceed to offense if ThreatDetector says it's safe.
        # Otherwise, hold back and wait.
        # ══════════════════════════════════════════════════════════
        if not self.threat.is_safe_to_attack():
            self._default_guard()
            return "GUARDING [not safe]"

        # ══════════════════════════════════════════════════════════
        # PRIORITY 5: FATAL BLOW (low HP)
        # ══════════════════════════════════════════════════════════
        if not self.fatal_used and p1['hp'] < 0.30 and dist < self.MID_DIST:
            do("FATAL", self.fwd, self.bwd)
            self.fatal_used = True
            self.cd = COOLDOWN["fatal"]
            return "FATAL BLOW"

        # ══════════════════════════════════════════════════════════
        # PRIORITY 6: ANTI-AIR
        # Opponent is airborne and in range — D2 them.
        # ══════════════════════════════════════════════════════════
        if airborne and dist < self.MID_DIST:
            combo_d2_antiair(self.fwd, self.bwd)
            self.cd = COOLDOWN["d2_aa"]
            return "D2→JUGGLE [anti-air]"

        # ══════════════════════════════════════════════════════════
        # PRIORITY 7: OFFENSE — distance-based
        # Safe window confirmed. Choose moves based on range.
        # ══════════════════════════════════════════════════════════

        # ── FULL SCREEN ───────────────────────────────────────────
        if dist > self.FULL_DIST:
            return self._offense_fullscreen()

        # ── FAR RANGE ─────────────────────────────────────────────
        if dist > self.FAR_DIST:
            return self._offense_far()

        # ── MID RANGE ─────────────────────────────────────────────
        if dist > self.PB_DIST:
            return self._offense_mid(p1, p2, dist)

        # ── POINT BLANK ───────────────────────────────────────────
        return self._offense_pointblank(p1, p2, dist)

    # ══════════════════════════════════════════════════════════════════
    # OFFENSE ROUTINES — organized by distance
    # ══════════════════════════════════════════════════════════════════

    def _offense_fullscreen(self):
        """Full screen: close distance. Teleport, dash, or throw a
        projectile to cover the approach."""
        f, b = self.fwd, self.bwd
        r = np.random.random()

        if r < 0.45:
            do("DD3", f, b)
            self.cd = COOLDOWN["teleport"]
            return "TELEPORT IN [fullscreen]"

        if r < 0.70:
            # Double dash
            _press([f, f], 3, 0)
            _press([f, f], 3, 0)
            self.cd = COOLDOWN["dash"]
            return "DASH DASH [fullscreen]"

        if r < 0.85:
            do("DF1", f, b)
            self.cd = COOLDOWN["bagbomb"]
            return "Bag Bomb [fullscreen]"

        do("BF2", f, b)
        self.cd = COOLDOWN["mace"]
        return "Demonic Mace [fullscreen]"

    def _offense_far(self):
        """Far range: prioritize teleport to get in. Mix with projectiles."""
        f, b = self.fwd, self.bwd
        r = np.random.random()

        if r < 0.40:
            do("DD3", f, b)
            self.cd = COOLDOWN["teleport"]
            return "TELEPORT [far]"

        if r < 0.55:
            _press([f, f], 3, 0)
            _press([f, f], 3, 0)
            self.cd = COOLDOWN["dash"]
            return "DASH DASH [far]"

        if r < 0.70:
            do("DF1", f, b)
            self.cd = COOLDOWN["bagbomb"]
            return "Bag Bomb [far]"

        if r < 0.80:
            do("BF2", f, b)
            self.cd = COOLDOWN["mace"]
            return "Demonic Mace [far]"

        if r < 0.90:
            do("BF4", f, b)
            self.cd = COOLDOWN["bola"]
            return "Damned Bola [far]"

        do("F3", f, b)
        self.cd = COOLDOWN["f3"]
        return "F3 [gap close]"

    def _offense_mid(self, p1, p2, dist):
        """Mid range: Kollector's sweet spot. Full combo potential.
        Uses weighted randomization with mixup-adjusted weights."""
        f, b = self.fwd, self.bwd

        # ── Kill confirm ──
        if p2['hp'] < 0.18:
            if dist < self.MID_DIST:
                combo_ravages_kill(f, b)
                self.cd = COOLDOWN["ravages_kill"]
                return "Ravages→CLUTCH [KILL CONFIRM]"

        # ── Mixup-forced options ──
        if self.mixup.should_force_oh():
            self.mixup.used_oh()
            combo_f2_overhead(f, b)
            self.cd = COOLDOWN["f2_oh"]
            return "F2→HOP2→DB3 [OH forced]"

        if self.mixup.should_force_low():
            self.mixup.used_low()
            combo_f12_juggle(f, b)
            self.cd = COOLDOWN["f12_juggle"]
            return "F1,2→HOP2→DB3 [low forced]"

        # ── Weighted random selection ──
        r = np.random.random()
        lw = self.mixup.low_weight()
        ow = self.mixup.oh_weight()

        cuts = np.cumsum([
            0.14,   # Ravages (launcher)
            lw,     # F1,2 low starter
            ow,     # F2 overhead starter
            0.09,   # B1,2 → Shotel
            0.07,   # 2,1,2 → Shotel
            0.06,   # B3,4 → Amp Bola
            0.05,   # F4,4 → Shotel (safe overhead string)
            0.05,   # B4,3 → Clutch
            0.04,   # F3 gap close
            0.04,   # 4 ranged poke
            0.04,   # B2 stagger
            0.03,   # D3 low check
            0.03,   # D4 low
            0.03,   # 1,3 → Shotel (fast punish)
            0.02,   # D1 fastest poke
            0.02,   # Throw (if close enough)
        ])
        cuts /= cuts[-1]  # normalize

        if r < cuts[0]:
            combo_ravages_standard(f, b)
            self.cd = COOLDOWN["ravages"]
            return "4,4,3→HOP2→DB3"

        if r < cuts[1]:
            self.mixup.used_low()
            combo_f12_juggle(f, b)
            self.cd = COOLDOWN["f12_juggle"]
            return "F1,2→HOP2→DB3 [low]"

        if r < cuts[2]:
            self.mixup.used_oh()
            combo_f2_overhead(f, b)
            self.cd = COOLDOWN["f2_oh"]
            return "F2→HOP2→DB3 [OH]"

        if r < cuts[3]:
            combo_b12_shotel(f, b)
            self.cd = COOLDOWN["b12_shotel"]
            return "B1,2→DB3"

        if r < cuts[4]:
            combo_212_shotel(f, b)
            self.cd = COOLDOWN["212_shotel"]
            return "2,1,2→DB3"

        if r < cuts[5]:
            combo_b34_amp_bola(f, b)
            self.cd = COOLDOWN["b34_amp"]
            return "B3,4→AmpBola"

        if r < cuts[6]:
            combo_f44_shotel(f, b)
            self.cd = COOLDOWN["f44_shotel"]
            return "F4,4→DB3 [safe OH]"

        if r < cuts[7]:
            combo_b43_clutch(f, b)
            self.cd = COOLDOWN["b43_clutch"]
            return "B4,3→Clutch"

        if r < cuts[8]:
            do("F3", f, b)
            self.cd = COOLDOWN["f3"]
            return "F3 [gap close]"

        if r < cuts[9]:
            do("4", f, b)
            self.cd = COOLDOWN["4"]
            return "4 [poke]"

        if r < cuts[10]:
            do("B2", f, b)
            self.cd = COOLDOWN["b2"]
            return "B2 [stagger]"

        if r < cuts[11]:
            self.mixup.used_low()
            do("D3", f, b)
            self.cd = COOLDOWN["d3"]
            return "D3 [low check]"

        if r < cuts[12]:
            self.mixup.used_low()
            do("D4", f, b)
            self.cd = COOLDOWN["d4"]
            return "D4 [low]"

        if r < cuts[13]:
            combo_13_shotel(f, b)
            self.cd = COOLDOWN["13_shotel"]
            return "1,3→DB3 [fast]"

        if r < cuts[14]:
            do("D1", f, b)
            self.cd = COOLDOWN["d1"]
            return "D1 [poke]"

        if dist < self.THROW_DIST:
            self.mixup.used_throw()
            do("THROW_F", f, b)
            self.cd = COOLDOWN["throw"]
            return "Throw"

        # Fallback: walk forward
        _press([self.fwd], 4, 0)
        self.cd = 1
        return "WALK IN"

    def _offense_pointblank(self, p1, p2, dist):
        """Point blank: maximum mixup territory. Alternate between
        lows, overheads, throws, and command grabs."""
        f, b = self.fwd, self.bwd

        # ── Kill confirm ──
        if p2['hp'] < 0.18:
            combo_ravages_kill(f, b)
            self.cd = COOLDOWN["ravages_kill"]
            return "Ravages→CLUTCH [KILL]"

        # ── Forced mixup shifts ──
        if self.mixup.should_force_oh():
            self.mixup.used_oh()
            combo_f2_overhead(f, b)
            self.cd = COOLDOWN["f2_oh"]
            return "F2→HOP2→DB3 [OH shift]"

        if self.mixup.should_force_low():
            self.mixup.used_low()
            do("F1", f, b)
            self.cd = COOLDOWN["f1"]
            return "F1 [low shift]"

        if self.mixup.should_force_grab() and dist < self.GRAB_DIST:
            self.mixup.used_grab()
            do("DBF3", f, b)
            self.cd = COOLDOWN["clutch"]
            return "Demonic Clutch [grab shift]"

        if self.mixup.should_force_throw() and dist < self.THROW_DIST:
            self.mixup.used_throw()
            r2 = np.random.random()
            do("THROW_F" if r2 < 0.5 else "THROW_B", f, b)
            self.cd = COOLDOWN["throw"]
            return "Throw [shift]"

        # ── Standard PB offense ──
        r = np.random.random()
        cuts = np.cumsum([
            0.12,   # F2 overhead combo
            0.12,   # F1 low
            0.10,   # Ravages
            0.08,   # Throw
            0.07,   # D1 poke
            0.07,   # D4 low
            0.06,   # Demonic Clutch
            0.06,   # B4,3 → Clutch
            0.06,   # 1,3 → Shotel
            0.05,   # B1,2 → Shotel
            0.04,   # D3 low check
            0.04,   # 2,1,2 → Shotel
            0.04,   # F4,4 → Shotel
            0.03,   # B2 stagger
            0.03,   # F1,2 throw ender
            0.02,   # Back throw
            0.01,   # Walk forward
        ])
        cuts /= cuts[-1]

        if r < cuts[0]:
            self.mixup.used_oh()
            combo_f2_overhead(f, b)
            self.cd = COOLDOWN["f2_oh"]
            return "F2→HOP2→DB3 [OH]"

        if r < cuts[1]:
            self.mixup.used_low()
            do("F1", f, b)
            self.cd = COOLDOWN["f1"]
            return "F1 [low]"

        if r < cuts[2]:
            combo_ravages_standard(f, b)
            self.cd = COOLDOWN["ravages"]
            return "4,4,3→HOP2→DB3"

        if r < cuts[3] and dist < self.THROW_DIST:
            self.mixup.used_throw()
            do("THROW_F", f, b)
            self.cd = COOLDOWN["throw"]
            return "Throw"

        if r < cuts[4]:
            do("D1", f, b)
            self.cd = COOLDOWN["d1"]
            return "D1 [poke]"

        if r < cuts[5]:
            self.mixup.used_low()
            do("D4", f, b)
            self.cd = COOLDOWN["d4"]
            return "D4 [low]"

        if r < cuts[6] and dist < self.GRAB_DIST:
            self.mixup.used_grab()
            do("DBF3", f, b)
            self.cd = COOLDOWN["clutch"]
            return "Demonic Clutch"

        if r < cuts[7]:
            combo_b43_clutch(f, b)
            self.cd = COOLDOWN["b43_clutch"]
            return "B4,3→Clutch"

        if r < cuts[8]:
            combo_13_shotel(f, b)
            self.cd = COOLDOWN["13_shotel"]
            return "1,3→DB3"

        if r < cuts[9]:
            combo_b12_shotel(f, b)
            self.cd = COOLDOWN["b12_shotel"]
            return "B1,2→DB3"

        if r < cuts[10]:
            self.mixup.used_low()
            do("D3", f, b)
            self.cd = COOLDOWN["d3"]
            return "D3 [low]"

        if r < cuts[11]:
            combo_212_shotel(f, b)
            self.cd = COOLDOWN["212_shotel"]
            return "2,1,2→DB3"

        if r < cuts[12]:
            combo_f44_shotel(f, b)
            self.cd = COOLDOWN["f44_shotel"]
            return "F4,4→DB3"

        if r < cuts[13]:
            do("B2", f, b)
            self.cd = COOLDOWN["b2"]
            return "B2 [stagger]"

        if r < cuts[14]:
            combo_f12_throw(f, b)
            self.cd = COOLDOWN["f12_throw"]
            return "F1,2,1+3 [throw ender]"

        if r < cuts[15] and dist < self.THROW_DIST:
            self.mixup.used_throw()
            do("THROW_B", f, b)
            self.cd = COOLDOWN["throw"]
            return "Back Throw"

        _press([self.fwd], 4, 0)
        self.cd = 1
        return "WALK → throw range"

    # ══════════════════════════════════════════════════════════════════
    # PUNISH — after block releases
    # ══════════════════════════════════════════════════════════════════

    def _punish_after_block(self, dist, p2):
        """Called when block stance releases. Use fast moves to punish
        the opponent's recovery frames."""
        f, b = self.fwd, self.bwd

        # ── Kill confirm punish ──
        if p2['hp'] < 0.15 and dist < self.PB_DIST:
            combo_ravages_kill(f, b)
            self.cd = COOLDOWN["ravages_kill"]
            return "PUNISH: Ravages→CLUTCH [kill]"

        # ── Point blank punish ──
        if dist < self.PB_DIST:
            r = np.random.random()
            if r < 0.30:
                # Fastest full punish (8f startup)
                combo_13_shotel(f, b)
                self.cd = COOLDOWN["13_shotel"]
                return "PUNISH: 1,3→DB3 [8f]"
            if r < 0.50:
                combo_ravages_standard(f, b)
                self.cd = COOLDOWN["ravages"]
                return "PUNISH: Ravages→DB3"
            if r < 0.65:
                # D1 is 8f and safe
                do("D1", f, b)
                self.cd = COOLDOWN["d1"]
                return "PUNISH: D1 [8f safe]"
            if r < 0.80:
                combo_b12_shotel(f, b)
                self.cd = COOLDOWN["b12_shotel"]
                return "PUNISH: B1,2→DB3"
            combo_212_shotel(f, b)
            self.cd = COOLDOWN["212_shotel"]
            return "PUNISH: 2,1,2→DB3"

        # ── Mid range punish ──
        if dist < self.MID_DIST:
            r = np.random.random()
            if r < 0.40:
                do("4", f, b)
                self.cd = COOLDOWN["4"]
                return "PUNISH: 4 [ranged poke]"
            if r < 0.70:
                do("F3", f, b)
                self.cd = COOLDOWN["f3"]
                return "PUNISH: F3"
            combo_b34_amp_bola(f, b)
            self.cd = COOLDOWN["b34_amp"]
            return "PUNISH: B3,4→AmpBola"

        # ── Far punish: close distance ──
        do("DD3", f, b)
        self.cd = COOLDOWN["teleport"]
        return "PUNISH: TELEPORT IN"

    # ══════════════════════════════════════════════════════════════════
    # RESET (between rounds)
    # ══════════════════════════════════════════════════════════════════

    def reset(self):
        """Reset state between rounds."""
        self.cd = 0
        self.blocking = False
        self.block_low = False
        self.block_timer = 0
        self.fatal_used = False
        self.threat.reset()
        self.mixup.reset()


# ═══════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  KOLLECTOR BOT v12 — Block-First Architecture")
    print("=" * 70)
    print()
    print("  DEFAULT STATE: Hold back (blocking)")
    print("  THREAT DETECTION: HP drop | approach velocity | distance | input")
    print("  OFFENSE: Only when safe window confirmed")
    print("  STRINGS: 12-frame inter-hit gap for proper MK11 linking")
    print("  MOVESET: Full Kollector moveset with all combo routes")
    print()

    vision = VisionEngine()
    vision.start()

    print(">> Waiting for match lock...")
    while not vision.ready:
        time.sleep(0.1)
    print(">> Locked.\n")

    bot  = KollectorBot()
    tick = time.time()

    try:
        while True:
            # ── Frame timing ──
            elapsed = time.time() - tick
            if elapsed < FRAME:
                time.sleep(FRAME - elapsed)
            tick = time.time()

            # ── Read game state ──
            state = vision.get_state()
            if not state:
                continue

            p1, p2 = state["p1"], state["p2"]
            action = bot.decide(p1, p2)

            # ── Skip printing for continuous states ──
            if action in ("GUARDING", "GUARDING [not safe]", "HOLDING BLOCK"):
                continue

            # ── Print status ──
            dist = abs(p1['x'] - p2['x'])
            dmg  = bot.threat.frames_since_our_dmg
            appr = bot.threat.opp_approach_frames
            print(
                f"Dist:{dist:>5.0f} | "
                f"KOL:{p1['hp']*1000:>4.0f} | "
                f"OPP:{p2['hp']*1000:>4.0f} | "
                f"Dmg:{dmg:>3} | "
                f"Apr:{appr:>2} | "
                f"BT:{bot.block_timer:>3} | "
                f"CD:{bot.cd:>2} | "
                f"L:{bot.mixup.low_count} O:{bot.mixup.oh_count} "
                f"T:{bot.mixup.throw_count} G:{bot.mixup.grab_count} | "
                f"{action}"
            )

            # ── Round over detection ──
            if p1['hp'] <= 0.01 or p2['hp'] <= 0.01:
                print("\n>> Round over.\n")
                gamepad.reset()
                gamepad.update()
                bot.reset()
                time.sleep(2.5)

    except KeyboardInterrupt:
        print("\n>> Bot offline.")
    finally:
        gamepad.reset()
        gamepad.update()
        vision.running = False
        vision.join()