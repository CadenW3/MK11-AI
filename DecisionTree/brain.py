"""
kollector_bot_v9.py  —  Fixed blocking + aggressive offense

Root cause fixes from v8:
  - BLOCK = HOLD BACK. Period. No release+repress "flawless" attempt.
    The 1-frame release was dropping guard and eating hits.
  - REMOVED predicted blocks entirely. They caused a death loop:
    predict→block→release→F3 punish→get hit→predict→block→repeat.
    Now only blocks on ACTUAL opponent input read (button currently pressed).
  - Block hold extended to 40 frames. Only releases when opponent
    has NOT pressed attack for 8+ consecutive frames.
  - Punish uses D1 (8f) or 1,3→DB3 (8f) instead of F3 (11f).
    F3 was getting stuffed every single time.
  - During cooldown: hold back (passive block).
  - Removed block-punish oscillation: after punish, go to offense, not back to block.
"""

import time
import numpy as np
import vgamepad as vg
from collections import deque
from DMA import VisionEngine

gamepad = vg.VX360Gamepad()
FRAME = 1.0 / 60.0

BTN   = vg.XUSB_BUTTON
UP    = BTN.XUSB_GAMEPAD_DPAD_UP
DOWN  = BTN.XUSB_GAMEPAD_DPAD_DOWN
LEFT  = BTN.XUSB_GAMEPAD_DPAD_LEFT
RIGHT = BTN.XUSB_GAMEPAD_DPAD_RIGHT
B1    = BTN.XUSB_GAMEPAD_X
B2    = BTN.XUSB_GAMEPAD_Y
B3    = BTN.XUSB_GAMEPAD_A
B4    = BTN.XUSB_GAMEPAD_B
LB    = BTN.XUSB_GAMEPAD_LEFT_SHOULDER
RB    = BTN.XUSB_GAMEPAD_RIGHT_SHOULDER

INP_UP   = 1
INP_DOWN = 2
INP_LEFT = 4
INP_RGT  = 8
INP_FP   = 64
INP_BP   = 16
INP_FK   = 32
INP_BK   = 128
INP_THRW = 4096
INP_ATK  = INP_FP | INP_BP | INP_FK | INP_BK

def inp_attacking(m):    return bool(m & INP_ATK)
def inp_low_attack(m):   return bool(m & INP_DOWN) and bool(m & INP_ATK)
def inp_jump_attack(m):  return bool(m & INP_UP) and bool(m & INP_ATK)
def inp_jump(m):         return bool(m & INP_UP) and not bool(m & INP_ATK)
def inp_throw(m):        return bool(m & INP_THRW)


# ═══════════════════════════════════════════════════════════════
# PRIMITIVES
# ═══════════════════════════════════════════════════════════════
def _press(btns, hold=1, gap=0):
    gamepad.reset()
    for b in btns:
        if b: gamepad.press_button(b)
    gamepad.update()
    time.sleep(FRAME * max(1, hold))
    gamepad.reset(); gamepad.update()
    if gap: time.sleep(FRAME * gap)

def _hold_back(bwd, low=False):
    """Hold back direction to block. No reset — additive."""
    gamepad.reset()
    if low:
        gamepad.press_button(DOWN)
    gamepad.press_button(bwd)
    gamepad.update()

def release():
    gamepad.reset(); gamepad.update()

def _motion(dirs, btn, gap=0):
    for d in dirs:
        gamepad.reset()
        if d: gamepad.press_button(d)
        gamepad.update()
        time.sleep(FRAME)
    gamepad.reset()
    if btn: gamepad.press_button(btn)
    gamepad.update()
    time.sleep(FRAME)
    gamepad.reset(); gamepad.update()
    if gap: time.sleep(FRAME * gap)

def do(key, fwd, bwd, gap=0):
    match key:
        case "1":     _press([B1], 1, gap)
        case "2":     _press([B2], 1, gap)
        case "3":     _press([B3], 1, gap)
        case "4":     _press([B4], 1, gap)
        case "F1":    _press([fwd, B1], 1, gap)
        case "F2":    _press([fwd, B2], 1, gap)
        case "F3":    _press([fwd, B3], 1, gap)
        case "F4":    _press([fwd, B4], 1, gap)
        case "B1":    _press([bwd, B1], 1, gap)
        case "B2":    _press([bwd, B2], 1, gap)
        case "B3":    _press([bwd, B3], 1, gap)
        case "B4":    _press([bwd, B4], 1, gap)
        case "D1":    _press([DOWN, B1], 1, gap)
        case "D2":    _press([DOWN, B2], 1, gap)
        case "D3":    _press([DOWN, B3], 1, gap)
        case "D4":    _press([DOWN, B4], 1, gap)
        case "DB3":   _motion([DOWN, bwd], B3, gap)
        case "DB3A":  _motion([DOWN, bwd], B3); time.sleep(FRAME); _press([RB], 1, gap)
        case "DBF3":  _motion([DOWN, bwd, fwd], B3, gap)
        case "DF1":   _motion([DOWN, fwd], B1, gap)
        case "DF1F":  _motion([DOWN, fwd], B1); _press([fwd], 1, gap)
        case "BF2":   _motion([bwd, fwd], B2, gap)
        case "BF4":   _motion([bwd, fwd], B4, gap)
        case "BF4A":  _motion([bwd, fwd], B4); time.sleep(FRAME); _press([RB], 1, gap)
        case "DB4":   _motion([DOWN, bwd], B4, gap)
        case "DB1":   _motion([DOWN, bwd], B1, gap)
        case "DD3":   _press([DOWN], 1, 0); _press([DOWN, B3], 1, gap)
        case "DD3F":  _press([DOWN], 1, 0); _press([DOWN, B3], 1, 0); _press([fwd], 1, gap)
        case "THROW_F": _press([fwd, B1, B3], 1, gap)
        case "THROW_B": _press([bwd, B1, B3], 1, gap)
        case "FATAL":   _press([LB, RB], 2, gap)
        case _: pass


# ═══════════════════════════════════════════════════════════════
# KOMBO STRINGS
# ═══════════════════════════════════════════════════════════════
def string_13(f, b):
    _press([B1], 1, 0); _press([B3], 1, 0)

def string_f12(f, b):
    _press([f, B1], 1, 0); _press([B2], 1, 0)

def string_b12(f, b):
    _press([b, B1], 1, 0); _press([B2], 1, 0)

def string_443(f, b):
    _press([B4], 1, 0); _press([B4], 1, 0); _press([B3], 1, 1)

def string_b34(f, b):
    _press([b, B3], 1, 0); _press([B4], 1, 0)

def string_b43(f, b):
    _press([b, B4], 1, 0); _press([B3], 1, 0)

def string_f44(f, b):
    _press([f, B4], 1, 0); _press([B4], 1, 0)

def string_212(f, b):
    _press([B2], 1, 0); _press([B1], 1, 0); _press([B2], 1, 0)


# ═══════════════════════════════════════════════════════════════
# JUGGLE ENDERS
# ═══════════════════════════════════════════════════════════════
def juggle_hop2_db3(f, b):
    _press([UP, B2], 2, 0)
    time.sleep(FRAME * 4)
    _motion([DOWN, b], B3, 0)

def juggle_hop2_dbf3(f, b):
    _press([UP, B2], 2, 0)
    time.sleep(FRAME * 4)
    _motion([DOWN, b, f], B3, 0)

def juggle_hop2_db3a(f, b):
    _press([UP, B2], 2, 0)
    time.sleep(FRAME * 4)
    _motion([DOWN, b], B3, 0)
    time.sleep(FRAME)
    _press([RB], 1, 0)


# ═══════════════════════════════════════════════════════════════
# COMBO ROUTES
# ═══════════════════════════════════════════════════════════════
def combo_ravages(f, b, kill=False):
    string_443(f, b)
    if kill: juggle_hop2_dbf3(f, b)
    else:    juggle_hop2_db3(f, b)

def combo_f12(f, b):
    string_f12(f, b); juggle_hop2_db3(f, b)

def combo_f2_oh(f, b):
    _press([f, B2], 1, 1); juggle_hop2_db3(f, b)

def combo_d2_aa(f, b):
    _press([DOWN, B2], 1, 1); juggle_hop2_db3a(f, b)

def combo_b12(f, b):
    string_b12(f, b); _motion([DOWN, b], B3, 0)

def combo_13(f, b):
    string_13(f, b); _motion([DOWN, b], B3, 0)

def combo_b34(f, b):
    string_b34(f, b); _motion([b, f], B4, 0)
    time.sleep(FRAME); _press([RB], 1, 0)

def combo_212(f, b):
    string_212(f, b); _motion([DOWN, b], B3, 0)

def combo_f44(f, b):
    string_f44(f, b); _motion([DOWN, b], B3, 0)

def combo_b43(f, b):
    string_b43(f, b); _motion([DOWN, b, f], B3, 0)


# ═══════════════════════════════════════════════════════════════
# COOLDOWNS
# ═══════════════════════════════════════════════════════════════
CD = {
    "ravages": 16, "ravages_kill": 22,
    "f12": 14, "f2_oh": 14, "d2_aa": 12,
    "b12": 12, "combo13": 10, "b34": 14,
    "combo212": 12, "f44": 14, "b43": 12,
    "d3": 3, "d4": 3, "d1": 3, "d2": 5,
    "1": 3, "2": 4, "3": 3, "4": 4,
    "f1": 4, "f2": 5, "f3": 4, "f4": 5,
    "b1": 4, "b2": 3, "b3": 5, "b4": 5,
    "throw": 6, "clutch": 8,
    "bagbomb": 8, "far_bagbomb": 10,
    "mace": 10, "bola": 8,
    "shotel": 7, "vial": 8,
    "teleport": 8, "fatal": 12,
}


# ═══════════════════════════════════════════════════════════════
# TRACKER
# ═══════════════════════════════════════════════════════════════
class Tracker:
    def __init__(self):
        self.p1_hp = deque([1.0]*12, maxlen=12)
        self.p2_hp = deque([1.0]*12, maxlen=12)
        self.p2_y  = deque([0.0]*8,  maxlen=8)
        self.inp_hist = deque([0]*16, maxlen=16)

    def update(self, p1, p2):
        self.p1_hp.append(p1['hp'])
        self.p2_hp.append(p2['hp'])
        self.p2_y.append(p2['y'])
        self.inp_hist.append(p2.get('inputs', 0))

    def we_took_damage(self):
        h = list(self.p1_hp)
        return h[-5] - h[-1] > 0.003

    def opp_airborne(self):
        return max(list(self.p2_y)[-4:]) > 20.0

    def opp_inp(self):
        return self.inp_hist[-1]

    def opp_idle_frames(self):
        """Count consecutive frames with no attack input (from most recent)."""
        count = 0
        for m in reversed(self.inp_hist):
            if inp_attacking(m) or inp_throw(m):
                break
            count += 1
        return count

    def opp_attacking_recently(self):
        """True if opponent pressed attack in last 4 frames."""
        return any(inp_attacking(m) for m in list(self.inp_hist)[-4:])


# ═══════════════════════════════════════════════════════════════
# KOLLECTOR BOT v9
# ═══════════════════════════════════════════════════════════════
class KollectorBot:
    THROW_DIST = 120
    GRAB_DIST  = 135
    PB_DIST    = 170
    MID_DIST   = 355
    FAR_DIST   = 520
    FULL_DIST  = 700

    # Block hold: hold for this many frames MINIMUM, then check idle
    BLOCK_MIN_HOLD   = 30
    BLOCK_IDLE_NEED  = 8    # opponent must be idle this many frames to release

    def __init__(self):
        self.cd          = 0
        self.blocking    = False
        self.block_low   = False
        self.block_timer = 0     # frames spent blocking
        self.fwd         = RIGHT
        self.bwd         = LEFT
        self.fatal_used  = False
        self.tracker     = Tracker()
        self.low_count   = 0
        self.oh_count    = 0
        self.throw_count = 0
        self.grab_count  = 0
        self.tick_count  = 0
        self.just_punished = False  # prevent block→punish→block loop

    def _facing(self, p1, p2):
        self.fwd, self.bwd = (RIGHT, LEFT) if p1['x'] < p2['x'] else (LEFT, RIGHT)

    @staticmethod
    def _dist(p1, p2):
        return abs(p1['x'] - p2['x'])

    # ── BLOCKING ──────────────────────────────────────────

    def _start_block(self, low=False):
        """Start blocking. NO release. Just hold back."""
        self.blocking    = True
        self.block_low   = low
        self.block_timer = 0
        self.just_punished = False
        _hold_back(self.bwd, low=low)

    def _tick_block(self, opp_inp, dist):
        """Hold block each frame. Only release when safe."""
        self.block_timer += 1

        # Update high/low based on live input
        if inp_attacking(opp_inp):
            self.block_low = inp_low_attack(opp_inp)

        # Keep holding
        _hold_back(self.bwd, low=self.block_low)

        # Too far — release
        if dist > self.MID_DIST + 100:
            self.blocking = False
            release()
            return False

        # Only release if:
        #   1. We've held for at least BLOCK_MIN_HOLD frames
        #   2. Opponent has been idle for BLOCK_IDLE_NEED frames
        if (self.block_timer >= self.BLOCK_MIN_HOLD and
                self.tracker.opp_idle_frames() >= self.BLOCK_IDLE_NEED):
            self.blocking = False
            release()
            return False

        # Safety cap — don't block forever (80 frames = 1.3 seconds)
        if self.block_timer >= 80:
            self.blocking = False
            release()
            return False

        return True

    def _guard(self):
        """Passive guard during cooldown — just hold back."""
        _hold_back(self.bwd)

    def _decay(self):
        self.tick_count += 1
        if self.tick_count % 40 == 0:
            self.low_count   = max(0, self.low_count - 1)
            self.oh_count    = max(0, self.oh_count - 1)
            self.throw_count = max(0, self.throw_count - 1)
            self.grab_count  = max(0, self.grab_count - 1)

    # ── MAIN DECIDE ───────────────────────────────────────

    def decide(self, p1, p2):
        self._facing(p1, p2)
        self.tracker.update(p1, p2)
        self._decay()

        dist    = self._dist(p1, p2)
        opp_inp = self.tracker.opp_inp()
        airborne = self.tracker.opp_airborne()

        # ══════════════════════════════════════════════════
        # LAYER 1: INPUT-READ BLOCKING (actual input only)
        # Only trigger on REAL attack input — no predictions.
        # ══════════════════════════════════════════════════
        if not self.blocking and not self.just_punished and dist < self.MID_DIST + 50 and self.cd <= 1:

            # Throw tech
            if inp_throw(opp_inp) and dist < self.PB_DIST + 20:
                _press([UP], 1)
                self.cd = 3
                return "TECH THROW"

            # Jump attack → anti-air
            if inp_jump_attack(opp_inp) and dist < self.MID_DIST:
                combo_d2_aa(self.fwd, self.bwd)
                self.cd = CD["d2_aa"]
                return "D2→JUGGLE [AA read]"

            # Low attack → block low
            if inp_low_attack(opp_inp):
                self._start_block(low=True)
                return "BLOCK LOW [input read]"

            # Any attack → block high
            if inp_attacking(opp_inp):
                self._start_block(low=False)
                return "BLOCK HIGH [input read]"

        # ══════════════════════════════════════════════════
        # LAYER 2: HOLD BLOCK
        # ══════════════════════════════════════════════════
        if self.blocking:
            still = self._tick_block(opp_inp, dist)
            if still:
                return "HOLDING BLOCK"
            # Block released — punish
            self.cd = 0
            self.just_punished = True
            return self._punish(dist, p2)

        # ══════════════════════════════════════════════════
        # LAYER 3: REACTIVE BLOCK (we took damage)
        # ══════════════════════════════════════════════════
        if self.tracker.we_took_damage() and self.cd <= 2 and not self.just_punished:
            self._start_block(low=inp_low_attack(opp_inp))
            return "BLOCK [reactive]"

        # ══════════════════════════════════════════════════
        # LAYER 4: COOLDOWN — hold back (passive block)
        # ══════════════════════════════════════════════════
        if self.cd > 0:
            self.cd -= 1
            self._guard()
            return "GUARDING"

        # Reset punish flag once we're ready to act
        self.just_punished = False

        # ══════════════════════════════════════════════════
        # LAYER 5: FATAL BLOW
        # ══════════════════════════════════════════════════
        if not self.fatal_used and p1['hp'] < 0.30 and dist < self.MID_DIST:
            do("FATAL", self.fwd, self.bwd)
            self.fatal_used = True
            self.cd = CD["fatal"]
            return "FATAL BLOW"

        # ══════════════════════════════════════════════════
        # LAYER 6: ANTI-AIR
        # ══════════════════════════════════════════════════
        if airborne and dist < self.MID_DIST:
            combo_d2_aa(self.fwd, self.bwd)
            self.cd = CD["d2_aa"]
            return "D2→JUGGLE [AA]"

        # ══════════════════════════════════════════════════
        # LAYER 7: OFFENSE (distance-based)
        # ══════════════════════════════════════════════════

        # ── FULL SCREEN ───────────────────────────────────
        if dist > self.FULL_DIST:
            r = np.random.random()
            if r < 0.50:
                do("DD3", self.fwd, self.bwd)
                self.cd = CD["teleport"]
                return "TELEPORT IN"
            if r < 0.75:
                _press([self.fwd, self.fwd], 3, 0)
                _press([self.fwd, self.fwd], 3, 0)
                self.cd = 1
                return "DASH DASH"
            do("DF1", self.fwd, self.bwd)
            self.cd = CD["bagbomb"]
            return "Bag Bomb"

        # ── FAR ───────────────────────────────────────────
        if dist > self.FAR_DIST:
            r = np.random.random()
            if r < 0.45:
                do("DD3", self.fwd, self.bwd)
                self.cd = CD["teleport"]
                return "TELEPORT"
            if r < 0.65:
                _press([self.fwd, self.fwd], 3, 0)
                _press([self.fwd, self.fwd], 3, 0)
                self.cd = 1
                return "DASH DASH"
            if r < 0.80:
                do("DF1", self.fwd, self.bwd)
                self.cd = CD["bagbomb"]
                return "Bag Bomb"
            if r < 0.90:
                do("BF2", self.fwd, self.bwd)
                self.cd = CD["mace"]
                return "Demonic Mace"
            do("F3", self.fwd, self.bwd)
            self.cd = CD["f3"]
            return "F3"

        # ── MID ───────────────────────────────────────────
        if dist > self.PB_DIST:
            return self._mid_offense(p1, p2, dist)

        # ── POINT BLANK ───────────────────────────────────
        return self._pb_offense(p1, p2, dist)

    # ── MID RANGE ─────────────────────────────────────────

    def _mid_offense(self, p1, p2, dist):
        f, b = self.fwd, self.bwd

        if p2['hp'] < 0.18:
            combo_ravages(f, b, kill=True)
            self.cd = CD["ravages_kill"]
            return "Ravages→CLUTCH [kill]"

        r = np.random.random()
        low_w = max(0.04, 0.16 - self.low_count * 0.04)
        oh_w  = max(0.04, 0.14 - self.oh_count * 0.04)

        cuts = np.cumsum([
            0.16,  low_w, oh_w,
            0.10, 0.08, 0.07, 0.06, 0.05,
            0.04, 0.04, 0.04, 0.03, 0.03, 0.03, 0.02
        ])
        cuts /= cuts[-1]

        if r < cuts[0]:
            combo_ravages(f, b); self.cd = CD["ravages"]; return "4,4,3→HOP2→DB3"
        if r < cuts[1]:
            self.low_count += 1; combo_f12(f, b); self.cd = CD["f12"]; return "F1,2→HOP2→DB3 [low]"
        if r < cuts[2]:
            self.oh_count += 1; combo_f2_oh(f, b); self.cd = CD["f2_oh"]; return "F2→HOP2→DB3 [OH]"
        if r < cuts[3]:
            combo_b12(f, b); self.cd = CD["b12"]; return "B1,2→DB3"
        if r < cuts[4]:
            combo_212(f, b); self.cd = CD["combo212"]; return "2,1,2→DB3"
        if r < cuts[5]:
            combo_b34(f, b); self.cd = CD["b34"]; return "B3,4→AmpBola"
        if r < cuts[6]:
            combo_f44(f, b); self.cd = CD["f44"]; return "F4,4→DB3"
        if r < cuts[7]:
            combo_b43(f, b); self.cd = CD["b43"]; return "B4,3→Clutch"
        if r < cuts[8]:
            do("F3", f, b); self.cd = CD["f3"]; return "F3"
        if r < cuts[9]:
            do("4", f, b); self.cd = CD["4"]; return "4"
        if r < cuts[10]:
            do("B2", f, b); self.cd = CD["b2"]; return "B2"
        if r < cuts[11]:
            self.low_count += 1; do("D3", f, b); self.cd = CD["d3"]; return "D3 [low]"
        if r < cuts[12]:
            self.low_count += 1; do("D4", f, b); self.cd = CD["d4"]; return "D4 [low]"
        if r < cuts[13]:
            combo_13(f, b); self.cd = CD["combo13"]; return "1,3→DB3"
        do("D1", f, b); self.cd = CD["d1"]; return "D1"

    # ── POINT BLANK ───────────────────────────────────────

    def _pb_offense(self, p1, p2, dist):
        f, b = self.fwd, self.bwd

        if self.low_count >= 2:
            self.oh_count += 1; self.low_count = 0
            combo_f2_oh(f, b); self.cd = CD["f2_oh"]; return "F2→HOP2→DB3 [OH shift]"
        if self.oh_count >= 2:
            self.low_count += 1; self.oh_count = 0
            do("F1", f, b); self.cd = CD["f1"]; return "F1 [low shift]"
        if (self.low_count + self.oh_count) >= 3 and dist < self.GRAB_DIST:
            self.grab_count += 1; self.low_count = 0; self.oh_count = 0
            do("DBF3", f, b); self.cd = CD["clutch"]; return "Demonic Clutch [shift]"

        r = np.random.random()
        cuts = np.cumsum([
            0.13, 0.13, 0.11, 0.09, 0.08,
            0.07, 0.07, 0.06, 0.06, 0.05,
            0.04, 0.04, 0.03, 0.02, 0.02
        ])
        cuts /= cuts[-1]

        if r < cuts[0]:
            self.oh_count += 1; combo_f2_oh(f, b); self.cd = CD["f2_oh"]; return "F2→HOP2→DB3 [OH]"
        if r < cuts[1]:
            self.low_count += 1; do("F1", f, b); self.cd = CD["f1"]; return "F1 [low]"
        if r < cuts[2]:
            combo_ravages(f, b); self.cd = CD["ravages"]; return "4,4,3→HOP2→DB3"
        if r < cuts[3] and dist < self.THROW_DIST:
            self.throw_count += 1; do("THROW_F", f, b); self.cd = CD["throw"]; return "Throw"
        if r < cuts[4]:
            do("D1", f, b); self.cd = CD["d1"]; return "D1"
        if r < cuts[5]:
            self.low_count += 1; do("D4", f, b); self.cd = CD["d4"]; return "D4 [low]"
        if r < cuts[6] and dist < self.GRAB_DIST:
            self.grab_count += 1; do("DBF3", f, b); self.cd = CD["clutch"]; return "Demonic Clutch"
        if r < cuts[7]:
            combo_b43(f, b); self.cd = CD["b43"]; return "B4,3→Clutch"
        if r < cuts[8]:
            combo_13(f, b); self.cd = CD["combo13"]; return "1,3→DB3"
        if r < cuts[9]:
            combo_b12(f, b); self.cd = CD["b12"]; return "B1,2→DB3"
        if r < cuts[10]:
            self.low_count += 1; do("D3", f, b); self.cd = CD["d3"]; return "D3 [low]"
        if r < cuts[11]:
            combo_212(f, b); self.cd = CD["combo212"]; return "2,1,2→DB3"
        if r < cuts[12]:
            do("B2", f, b); self.cd = CD["b2"]; return "B2"
        if r < cuts[13] and dist < self.THROW_DIST:
            self.throw_count += 1; do("THROW_B", f, b); self.cd = CD["throw"]; return "Back Throw"
        do("F3", f, b); self.cd = CD["f3"]; return "F3"

    # ── PUNISH ────────────────────────────────────────────

    def _punish(self, dist, p2):
        """Fast punish after block. Use D1 or 1,3 — NOT F3."""
        f, b = self.fwd, self.bwd

        if p2['hp'] < 0.15 and dist < self.PB_DIST:
            combo_ravages(f, b, kill=True)
            self.cd = CD["ravages_kill"]; return "PUNISH: Ravages→CLUTCH"

        if dist < self.PB_DIST:
            r = np.random.random()
            if r < 0.40:
                # Fastest full punish: 1,3 is 8f startup
                combo_13(f, b)
                self.cd = CD["combo13"]; return "PUNISH: 1,3→DB3"
            if r < 0.65:
                combo_ravages(f, b)
                self.cd = CD["ravages"]; return "PUNISH: Ravages→DB3"
            if r < 0.80:
                # D1 is 8f, safe poke punish
                do("D1", f, b)
                self.cd = CD["d1"]; return "PUNISH: D1"
            combo_b12(f, b)
            self.cd = CD["b12"]; return "PUNISH: B1,2→DB3"

        if dist < self.MID_DIST:
            # At mid range after block, use 4 (ranged poke) not F3
            do("4", f, b)
            self.cd = CD["4"]; return "PUNISH: 4"

        # Far — teleport in
        do("DD3", f, b)
        self.cd = CD["teleport"]; return "PUNISH: TELEPORT"


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(">> Kollector Bot v9 — Fixed Blocking")
    print(">> Hold back (no release) | 30f min block | 8f idle release")
    print(">> No predicted blocks | Fast punishes | Passive guard in CD\n")

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
            elapsed = time.time() - tick
            if elapsed < FRAME:
                time.sleep(FRAME - elapsed)
            tick = time.time()

            state = vision.get_state()
            if not state:
                continue

            p1, p2 = state["p1"], state["p2"]
            action = bot.decide(p1, p2)

            if action in ("GUARDING", "HOLDING BLOCK"):
                continue

            dist    = abs(p1['x'] - p2['x'])
            opp_inp = p2.get('inputs', 0)
            idle    = bot.tracker.opp_idle_frames()
            print(
                f"Dist:{dist:>5.0f} | "
                f"KOL:{p1['hp']*1000:>4.0f} | "
                f"OPP:{p2['hp']*1000:>4.0f} | "
                f"Inp:{opp_inp:>5} | "
                f"Idle:{idle:>2} | "
                f"BT:{bot.block_timer:>2} | "
                f"CD:{bot.cd:>2} | "
                f"L:{bot.low_count} O:{bot.oh_count} | "
                f"{action}"
            )

            if p1['hp'] <= 0.01 or p2['hp'] <= 0.01:
                print("\n>> Round over.\n")
                gamepad.reset(); gamepad.update()
                bot = KollectorBot()
                time.sleep(2.5)

    except KeyboardInterrupt:
        print("\n>> Bot offline.")
    finally:
        gamepad.reset(); gamepad.update()
        vision.running = False
        vision.join()