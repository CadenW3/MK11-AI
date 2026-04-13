"""
scorpion_bot.py  —  Hyper-Aggressive Scorpion with RT Blocking

Same architecture as Kollector v12:
  - RT (Right Trigger) = dedicated block button
  - Input stream reads opponent buttons → block before hit lands
  - No safety gate — if not blocking and not in cooldown, ATTACK
  - Short cooldowns → relentless pressure
  - After every block → instant punish with full combo

SCORPION GAMEPLAN:
  - Mid range: B1 hit confirm into Hell Port (DB3) AMP combos
  - Teleport pressure: DB3 to cross up, AMP for launcher
  - Spear (BF1): ranged pull-in for combo or standalone punish
  - Low mixups: F4,2 (low starter) vs F3,2 (mid)
  - B1,4,3 is his safe go-to string
  - D2 anti-air into full juggle
  - Excellent throw game with forward throw KB

KEY STRINGS:
  2,1,2 — Main hit confirm (Mid,High,Mid) -7 on block
  B1,4,3 — Safe string (Mid,Low,High) -3 on block
  F3,2   — Advancing mid (Mid,Mid) -6 on block
  F3,4   — Advancing low (Mid,Low) KB trigger -16 UNSAFE
  F4,2   — Low starter (Low,Mid) -8 on block
  F4,2,4 — Low full string (Low,Mid,High) -12 UNSAFE
  1,1    — Torment (High,High) -5 on block, fast

SPECIAL MOVES:
  BF1    — Spear (High) — pulls in, combo ender
  BF1 A  — Amp Spear — extra damage
  DB3    — Hell Port (teleport behind, High) 23f startup
  DB3 A  — Amp Hell Port — LAUNCHES for full combo
  DF4    — Death Spin (Mid) — safe special, ender
  DB4    — Burning Spear (buff) — enhances fire damage
"""

import time
import numpy as np
import vgamepad as vg
from collections import deque
from DMA import (
    VisionEngine, has_attack, has_low_attack, has_jump_attack,
    has_throw, has_block, is_jumping, get_face_button,
    inputs_to_str, detect_special_motion,
    FACE_BUTTONS, DIRECTION_BUTTONS
)

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
LB    = BTN.XUSB_GAMEPAD_LEFT_SHOULDER
RB    = BTN.XUSB_GAMEPAD_RIGHT_SHOULDER

# ═══════════════════════════════════════════════════════════════════════
# BLOCKING PRIMITIVES — RT IS THE BLOCK BUTTON
# ═══════════════════════════════════════════════════════════════════════

def block_stand(bwd):
    """Standing block: RT + back direction. Blocks mids and highs."""
    gamepad.reset()
    gamepad.press_button(bwd)
    gamepad.right_trigger(255)
    gamepad.update()


def block_crouch(bwd):
    """Crouching block: RT + down + back. Blocks lows."""
    gamepad.reset()
    gamepad.press_button(bwd)
    gamepad.press_button(DOWN)
    gamepad.right_trigger(255)
    gamepad.update()


def block_auto(bwd, low=False):
    """Block high or low based on flag."""
    if low:
        block_crouch(bwd)
    else:
        block_stand(bwd)


def release():
    """Release everything — only call right before an attack input."""
    gamepad.reset()
    gamepad.right_trigger(0)
    gamepad.update()


# ═══════════════════════════════════════════════════════════════════════
# GAMEPAD PRIMITIVES
# ═══════════════════════════════════════════════════════════════════════

def _press(btns, hold=2, gap=0):
    """Press attack buttons. RT is released during this."""
    gamepad.reset()
    gamepad.right_trigger(0)  # release block
    for b in btns:
        if b: gamepad.press_button(b)
    gamepad.update()
    time.sleep(FRAME * max(1, hold))
    gamepad.reset()
    gamepad.right_trigger(0)
    gamepad.update()
    if gap > 0: time.sleep(FRAME * gap)

def _hold_back(bwd, low=False):
    """Legacy hold-back — now uses RT for actual blocking."""
    block_auto(bwd, low=low)

def _release():
    gamepad.reset(); gamepad.right_trigger(0); gamepad.update()

def _motion(dirs, btn, gap=0):
    """Motion input (QCB, QCF, etc). RT released during motion."""
    for d in dirs:
        gamepad.reset()
        gamepad.right_trigger(0)
        if d: gamepad.press_button(d)
        gamepad.update()
        time.sleep(FRAME * 2)
    gamepad.reset()
    gamepad.right_trigger(0)
    if btn: gamepad.press_button(btn)
    gamepad.update()
    time.sleep(FRAME * 2)
    gamepad.reset()
    gamepad.right_trigger(0)
    gamepad.update()
    if gap > 0: time.sleep(FRAME * gap)


# ═══════════════════════════════════════════════════════════════════════
# MOVE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════

def do(key, fwd, bwd, gap=0):
    match key:
        # ── Basic Attacks ──
        case "1":      _press([B1], 2, gap)           # Shin Kick — High, 7f
        case "2":      _press([B2], 2, gap)           # Straight Blade — Mid, 9f
        case "3":      _press([B3], 2, gap)           # Side Kick — Mid, 12f
        case "4":      _press([B4], 2, gap)           # Roundhouse — High, 11f
        # ── Forward Normals ──
        case "F1":     _press([fwd, B1], 2, gap)      # Gut Slice — Mid, 13f
        case "F2":     _press([fwd, B2], 2, gap)      # Flame Fist — Mid, 14f, long reach
        case "F3":     _press([fwd, B3], 2, gap)      # Quick Knee — Mid, 13f, advancing
        case "F4":     _press([fwd, B4], 2, gap)      # Shin Slash — Low, 16f
        # ── Back Normals ──
        case "B1":     _press([bwd, B1], 2, gap)      # Rising Cut — Mid, 9f, BEST MID
        case "B2":     _press([bwd, B2], 2, gap)      # Hell Punch — Mid, 15f, great reach
        case "B3":     _press([bwd, B3], 2, gap)      # Knee Strike — Mid
        case "B4":     _press([bwd, B4], 2, gap)      # Side Chop — Mid
        # ── Down Normals (Pokes) ──
        case "D1":     _press([DOWN, B1], 2, gap)     # Low Poke — Mid, 7f
        case "D2":     _press([DOWN, B2], 2, gap)     # Uppercut — High, 7f, anti-air
        case "D3":     _press([DOWN, B3], 2, gap)     # Low Kick — Low, 9f
        case "D4":     _press([DOWN, B4], 2, gap)     # Low Sweep — Low, 12f
        # ── Special Moves ──
        case "BF1":    _motion([bwd, fwd], B1, gap)   # Spear — High, pulls in
        case "BF1A":                                    # Amp Spear
            _motion([bwd, fwd], B1, 0)
            time.sleep(FRAME * 2)
            _press([RB], 2, gap)
        case "DB3":    _motion([DOWN, bwd], B3, gap)  # Hell Port — teleport, High
        case "DB3A":                                    # Amp Hell Port — LAUNCHER
            _motion([DOWN, bwd], B3, 0)
            time.sleep(FRAME * 2)
            _press([RB], 2, gap)
        case "DF4":    _motion([DOWN, fwd], B4, gap)  # Death Spin — Mid, safe ender
        case "DF4A":                                    # Amp Death Spin
            _motion([DOWN, fwd], B4, 0)
            time.sleep(FRAME * 2)
            _press([RB], 2, gap)
        case "DB4":    _motion([DOWN, bwd], B4, gap)  # Burning Spear — buff
        case "DB1":    _motion([DOWN, bwd], B1, gap)  # Demon Slam (if equipped)
        # ── Air specials ──
        case "AIR_DB3":                                 # Air Hell Port
            _motion([DOWN, bwd], B3, gap)
        # ── Throws ──
        case "THROW_F": _press([fwd, B1, B3], 2, gap)
        case "THROW_B": _press([bwd, B1, B3], 2, gap)
        # ── Fatal Blow ──
        case "FATAL":  _press([LB, RB], 3, gap)       # GET OVER HERE!
        case _: pass


# ═══════════════════════════════════════════════════════════════════════
# KOMBO STRINGS — with proper MK11 timing
# ═══════════════════════════════════════════════════════════════════════

HIT_GAP = 12    # frames between string hits
CANCEL_GAP = 4  # frames before special cancel

def string_11(f, b):
    """1,1 — Torment. High, High. -5 on block. Fast starter."""
    _press([B1], 2, HIT_GAP)
    _press([B1], 2, CANCEL_GAP)

def string_21(f, b):
    """2,1 — Eternal Vengeance. Mid, High. -5 on block.
    Main hit confirm — cancel into DB3 AMP on hit."""
    _press([B2], 2, HIT_GAP)
    _press([B1], 2, CANCEL_GAP)

def string_212(f, b):
    """2,1,2 — Wrath. Mid, High, Mid. -7 on block.
    Full string. Gap before last hit can be D2'd by opponent."""
    _press([B2], 2, HIT_GAP)
    _press([B1], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)

def string_b14(f, b):
    """B1,4 — Judgement. Mid, Low. -12 on block (unsafe).
    Low hit. Cancel into special on hit."""
    _press([b, B1], 2, HIT_GAP)
    _press([B4], 2, CANCEL_GAP)

def string_b143(f, b):
    """B1,4,3 — Haunted. Mid, Low, High. -3 on block (SAFE).
    Best safe string. Use as primary pressure tool."""
    _press([b, B1], 2, HIT_GAP)
    _press([B4], 2, HIT_GAP)
    _press([B3], 2, CANCEL_GAP)

def string_f32(f, b):
    """F3,2 — The Killing. Mid, Mid. -6 on block.
    Advancing string. Great for gap closing into pressure."""
    _press([f, B3], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)

def string_f34(f, b):
    """F3,4 — Mid, Low. -16 on block (VERY UNSAFE).
    Has Krushing Blow trigger. Use sparingly for mixup."""
    _press([f, B3], 2, HIT_GAP)
    _press([B4], 2, CANCEL_GAP)

def string_f42(f, b):
    """F4,2 — Soulless. Low, Mid. -8 on block.
    Low starter. Cancel into DB3 AMP on hit for combo."""
    _press([f, B4], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)

def string_f424(f, b):
    """F4,2,4 — Low, Mid, High. -12 on block (unsafe).
    Full low string. Don't use on block."""
    _press([f, B4], 2, HIT_GAP)
    _press([B2], 2, HIT_GAP)
    _press([B4], 2, CANCEL_GAP)


# ═══════════════════════════════════════════════════════════════════════
# COMBO ROUTES
#
# Scorpion's bread and butter:
#   [Starter] ~ DB3 AMP, F3, F3,2 ~ BF1
#   [Starter] ~ DB3 AMP, F3, F3,2 ~ DF4
#
# Starters: 2,1 / B1,4 / F3,2 / F4,2 / 1,1
# Enders:   BF1 (spear, knockdown), DF4 (death spin, safe)
# ═══════════════════════════════════════════════════════════════════════

# ── Hell Port AMP juggle extension ──
def _hellport_amp_juggle(f, b):
    """DB3 AMP → F3 → F3,2. Standard juggle after Hell Port launch."""
    _motion([DOWN, b], B3, 0)              # DB3 Hell Port
    time.sleep(FRAME * 2)
    _press([RB], 2, 4)                     # AMP — launches opponent
    _press([f, B3], 2, HIT_GAP)            # F3 — advancing reconnect
    _press([f, B3], 2, HIT_GAP)            # F3 again
    _press([B2], 2, CANCEL_GAP)            # ,2 — finishes F3,2 string

def _hellport_amp_juggle_short(f, b):
    """DB3 AMP → F3,2. Shorter/easier juggle."""
    _motion([DOWN, b], B3, 0)
    time.sleep(FRAME * 2)
    _press([RB], 2, 4)
    _press([f, B3], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)


# ── BnB midscreen combos ──

def combo_21_hellport_spear(f, b):
    """2,1 ~ DB3 AMP, F3, F3,2 ~ BF1. Main BnB. ~30% damage."""
    string_21(f, b)
    _hellport_amp_juggle(f, b)
    _motion([b, f], B1, 0)                 # BF1 Spear ender

def combo_21_hellport_spin(f, b):
    """2,1 ~ DB3 AMP, F3, F3,2 ~ DF4. Safe ender variant."""
    string_21(f, b)
    _hellport_amp_juggle(f, b)
    _motion([DOWN, f], B4, 0)              # DF4 Death Spin ender

def combo_21_hellport_kill(f, b):
    """2,1 ~ DB3 AMP, F3, F3,2 ~ BF1 AMP. Kill confirm. Max damage."""
    string_21(f, b)
    _hellport_amp_juggle(f, b)
    _motion([b, f], B1, 0)
    time.sleep(FRAME * 2)
    _press([RB], 2, 0)                     # Amp spear for extra damage

def combo_b14_hellport_spear(f, b):
    """B1,4 ~ DB3 AMP, F3, F3,2 ~ BF1. Safe starter BnB."""
    string_b14(f, b)
    _hellport_amp_juggle(f, b)
    _motion([b, f], B1, 0)

def combo_b14_hellport_spin(f, b):
    """B1,4 ~ DB3 AMP, F3,2 ~ DF4. Safe starter, safe ender."""
    string_b14(f, b)
    _hellport_amp_juggle_short(f, b)
    _motion([DOWN, f], B4, 0)

def combo_f32_hellport_spear(f, b):
    """F3,2 ~ DB3 AMP, F3, F3,2 ~ BF1. Advancing mid starter."""
    string_f32(f, b)
    _hellport_amp_juggle(f, b)
    _motion([b, f], B1, 0)

def combo_f42_hellport_spear(f, b):
    """F4,2 ~ DB3 AMP, F3, F3,2 ~ BF1. LOW starter combo."""
    string_f42(f, b)
    _hellport_amp_juggle(f, b)
    _motion([b, f], B1, 0)

def combo_f42_hellport_spin(f, b):
    """F4,2 ~ DB3 AMP, F3,2 ~ DF4. Low starter, safe ender."""
    string_f42(f, b)
    _hellport_amp_juggle_short(f, b)
    _motion([DOWN, f], B4, 0)

def combo_11_hellport_spear(f, b):
    """1,1 ~ DB3 AMP, F3, F3,2 ~ BF1. Fast starter."""
    string_11(f, b)
    _hellport_amp_juggle(f, b)
    _motion([b, f], B1, 0)

def combo_d2_antiair(f, b):
    """D2 (anti-air) ~ DB3 AMP, F3,2 ~ BF1. Anti-air full combo."""
    _press([DOWN, B2], 2, CANCEL_GAP)
    _hellport_amp_juggle_short(f, b)
    _motion([b, f], B1, 0)

def combo_d2_antiair_spin(f, b):
    """D2 ~ DB3 AMP, F3,2 ~ DF4. Anti-air safe ender."""
    _press([DOWN, B2], 2, CANCEL_GAP)
    _hellport_amp_juggle_short(f, b)
    _motion([DOWN, f], B4, 0)


# ── Standalone special cancels (no full juggle) ──

def combo_21_spear(f, b):
    """2,1 ~ BF1. Quick hit confirm into spear. Knockdown."""
    string_21(f, b)
    _motion([b, f], B1, 0)

def combo_b143_standalone(f, b):
    """B1,4,3 — safe string, no cancel needed. -3 on block."""
    string_b143(f, b)

def combo_212_spear(f, b):
    """2,1,2 ~ BF1. Full string into spear."""
    string_212(f, b)
    _motion([b, f], B1, 0)

def combo_212_spin(f, b):
    """2,1,2 ~ DF4. Full string into safe spin."""
    string_212(f, b)
    _motion([DOWN, f], B4, 0)

def combo_f32_spear(f, b):
    """F3,2 ~ BF1. Advancing into spear pull."""
    string_f32(f, b)
    _motion([b, f], B1, 0)

def combo_f32_spin(f, b):
    """F3,2 ~ DF4. Advancing into safe spin."""
    string_f32(f, b)
    _motion([DOWN, f], B4, 0)

def combo_f42_spear(f, b):
    """F4,2 ~ BF1. Low into spear."""
    string_f42(f, b)
    _motion([b, f], B1, 0)

def combo_b14_spear(f, b):
    """B1,4 ~ BF1. Mid-low into spear."""
    string_b14(f, b)
    _motion([b, f], B1, 0)

def combo_raw_spear(f, b):
    """Standalone BF1 spear. Ranged punish / whiff punish."""
    _motion([b, f], B1, 0)

def combo_raw_hellport(f, b):
    """Standalone DB3 teleport. Crosses up, high. Punishable if blocked."""
    _motion([DOWN, b], B3, 0)

def combo_raw_hellport_amp(f, b):
    """DB3 AMP → F3,2 ~ BF1. Raw teleport into full combo."""
    _motion([DOWN, b], B3, 0)
    time.sleep(FRAME * 2)
    _press([RB], 2, 4)
    _press([f, B3], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)
    _motion([b, f], B1, 0)


# ═══════════════════════════════════════════════════════════════════════
# COOLDOWNS
# ═══════════════════════════════════════════════════════════════════════

COOLDOWN = {
    # Full combos (hellport routes)
    "21_hp_spear":     10, "21_hp_spin":     10, "21_hp_kill":   12,
    "b14_hp_spear":    10, "b14_hp_spin":     9,
    "f32_hp_spear":    10, "f42_hp_spear":   10, "f42_hp_spin":   9,
    "11_hp_spear":     10, "d2_aa":           8, "d2_aa_spin":    8,
    # Quick cancels
    "21_spear":         6, "212_spear":       7, "212_spin":      7,
    "f32_spear":        6, "f32_spin":        6,
    "f42_spear":        6, "b14_spear":       6,
    "b143":             6,
    # Raw specials
    "raw_spear":        5, "raw_hp":          5, "raw_hp_amp":   10,
    "death_spin":       5, "burning_spear":   4,
    # Pokes
    "d1": 2, "d2": 3, "d3": 2, "d4": 2,
    "1": 2, "2": 2, "3": 2, "4": 2,
    # Directional normals
    "f1": 3, "f2": 3, "f3": 3, "f4": 3,
    "b1": 2, "b2": 3, "b3": 3,
    # Utility
    "throw": 4, "fatal": 8, "dash": 1,
}


# ═══════════════════════════════════════════════════════════════════════
# INPUT STREAM ANALYZER (from Kollector — properly reads DMA string inputs)
# ═══════════════════════════════════════════════════════════════════════

class InputStreamAnalyzer:
    """Reads opponent input stream for blocking and prediction.
    Uses DMA's string-based input helpers instead of raw bitmasks."""

    def __init__(self):
        self.input_history = deque(maxlen=30)
        self.our_hp   = deque([1.0]*20, maxlen=20)
        self.our_x    = deque([0.0]*20, maxlen=20)
        self.opp_x    = deque([0.0]*20, maxlen=20)
        self.opp_y    = deque([0.0]*20, maxlen=20)
        self.opp_hp   = deque([1.0]*20, maxlen=20)

        self.frames_since_our_dmg = 999
        self.frames_since_opp_dmg = 999
        self.last_our_hp = 1.0
        self.last_opp_hp = 1.0
        self.consecutive_dmg_frames = 0
        self.opp_approach_frames = 0
        self.opp_retreat_frames  = 0

        self.cur_inputs    = []
        self.cur_attacking = False
        self.cur_low       = False
        self.cur_jump_atk  = False
        self.cur_throw     = False
        self.cur_blocking  = False
        self.cur_special   = None

    def update(self, p1, p2):
        inputs = p2.get('inputs', [])
        self.cur_inputs = inputs
        self.input_history.append(inputs)

        self.our_hp.append(p1['hp'])
        self.our_x.append(p1['x'])
        self.opp_x.append(p2['x'])
        self.opp_y.append(p2['y'])
        self.opp_hp.append(p2['hp'])

        # Decode current opponent inputs via DMA string helpers
        self.cur_attacking = has_attack(inputs)
        self.cur_low       = has_low_attack(inputs)
        self.cur_jump_atk  = has_jump_attack(inputs)
        self.cur_throw     = has_throw(inputs)
        self.cur_blocking  = has_block(inputs)
        self.cur_special   = detect_special_motion(list(self.input_history), inputs)

        # Damage tracking
        cur_hp = p1['hp']
        if cur_hp < self.last_our_hp - 0.002:
            self.frames_since_our_dmg = 0
            self.consecutive_dmg_frames += 1
        else:
            self.frames_since_our_dmg = min(999, self.frames_since_our_dmg + 1)
            if self.frames_since_our_dmg > 4:
                self.consecutive_dmg_frames = 0
        self.last_our_hp = cur_hp

        opp_hp = p2['hp']
        if opp_hp < self.last_opp_hp - 0.002:
            self.frames_since_opp_dmg = 0
        else:
            self.frames_since_opp_dmg = min(999, self.frames_since_opp_dmg + 1)
        self.last_opp_hp = opp_hp

        # Approach tracking
        if len(self.opp_x) >= 4:
            ox, ux = list(self.opp_x), list(self.our_x)
            delta = abs(ox[-4]-ux[-4]) - abs(ox[-1]-ux[-1])
            if delta > 3.0:
                self.opp_approach_frames += 1; self.opp_retreat_frames = 0
            elif delta < -2.0:
                self.opp_retreat_frames += 1; self.opp_approach_frames = 0
            else:
                self.opp_approach_frames = max(0, self.opp_approach_frames - 1)
                self.opp_retreat_frames  = max(0, self.opp_retreat_frames - 1)

    # ── Query helpers (string-based, not bitmask) ──

    def atk_in_last_n(self, n=3):
        return any(has_attack(f) for f in list(self.input_history)[-n:])

    def low_in_last_n(self, n=3):
        return any(has_low_attack(f) for f in list(self.input_history)[-n:])

    def jump_in_last_n(self, n=4):
        return any(has_jump_attack(f) for f in list(self.input_history)[-n:])

    def throw_in_last_n(self, n=3):
        return any(has_throw(f) for f in list(self.input_history)[-n:])

    def should_block_low(self):
        if self.cur_low:
            return True
        if self.low_in_last_n(3):
            return True
        return False

    # ── Compat aliases used by ScorpionBot ──

    def we_took_damage_recently(self, frames=6):
        return self.frames_since_our_dmg <= frames

    def we_are_being_combod(self):
        return self.consecutive_dmg_frames >= 2

    def our_hp_is_stable(self, frames=20):
        return self.frames_since_our_dmg >= frames

    def opponent_approaching(self):
        return self.opp_approach_frames >= 3

    def opponent_rushing(self):
        if len(self.opp_x) < 4: return False
        ox, ux = list(self.opp_x), list(self.our_x)
        return abs(ox[-4]-ux[-4]) - abs(ox[-1]-ux[-1]) > 12.0

    def opponent_airborne(self):
        return max(list(self.opp_y)[-4:]) > 10.0

    def opponent_grounded_approaching(self):
        return self.opponent_approaching() and not self.opponent_airborne()

    def opp_blocking(self):
        return self.cur_blocking

    def is_safe_to_attack(self):
        if self.we_took_damage_recently(frames=8): return False
        if self.we_are_being_combod(): return False
        if self.opponent_rushing(): return False
        return True

    def should_block(self, dist):
        """Returns (should_block, is_low, reason)."""
        # Throw tech — must come before block checks
        if (self.cur_throw or self.throw_in_last_n(2)) and dist < 180:
            return False, False, "throw_tech"

        # Jump attack → anti-air opportunity
        if (self.cur_jump_atk or self.jump_in_last_n(3)) and dist < 400:
            return False, False, "anti_air"

        # Direct input read: face button pressed RIGHT NOW
        if self.cur_attacking and dist < 420:
            return True, self.cur_low, "input_read"

        # Recent attack in last 3 frames
        if self.atk_in_last_n(3) and dist < 400:
            return True, self.low_in_last_n(3), "recent_atk"

        # Special motion detected
        if self.cur_special and dist < 500:
            return True, False, f"special:{self.cur_special}"

        # Damage — block the string
        if self.we_took_damage_recently(12):
            return True, self.should_block_low(), "damage"

        # Being combod
        if self.we_are_being_combod():
            return True, self.should_block_low(), "combo"

        # Opponent rushing in
        if self.opp_approach_frames >= 5 and dist < 350:
            return True, self.should_block_low(), "rush"

        return False, False, ""

    def reset(self): self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# MIXUP TRACKER
# ═══════════════════════════════════════════════════════════════════════

class MixupTracker:
    def __init__(self):
        self.low_count = 0; self.mid_count = 0
        self.throw_count = 0; self.teleport_count = 0
        self.tick_counter = 0

    def tick(self):
        self.tick_counter += 1
        if self.tick_counter % 25 == 0:
            self.low_count      = max(0, self.low_count - 1)
            self.mid_count      = max(0, self.mid_count - 1)
            self.throw_count    = max(0, self.throw_count - 1)
            self.teleport_count = max(0, self.teleport_count - 1)

    def used_low(self):      self.low_count += 1
    def used_mid(self):      self.mid_count += 1
    def used_throw(self):    self.throw_count += 1
    def used_teleport(self): self.teleport_count += 1

    def should_force_low(self):    return self.mid_count >= 2
    def should_force_mid(self):    return self.low_count >= 2
    def should_force_throw(self):  return (self.low_count + self.mid_count) >= 3 and self.throw_count < 2

    def low_weight(self): return max(0.04, 0.16 - self.low_count * 0.04)
    def mid_weight(self): return max(0.04, 0.14 - self.mid_count * 0.04)

    def reset(self): self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# SCORPION BOT — BLOCK-FIRST
# ═══════════════════════════════════════════════════════════════════════

class ScorpionBot:
    THROW_DIST = 120
    PB_DIST    = 170
    MID_DIST   = 355
    FAR_DIST   = 520
    FULL_DIST  = 700

    def __init__(self):
        self.cd = 0
        self.blocking = False
        self.block_low = False
        self.block_timer = 0
        self.fwd = RIGHT
        self.bwd = LEFT
        self.fatal_used = False
        self.threat = InputStreamAnalyzer()
        self.mixup  = MixupTracker()

    def _facing(self, p1, p2):
        if p1['x'] < p2['x']: self.fwd, self.bwd = RIGHT, LEFT
        else:                  self.fwd, self.bwd = LEFT, RIGHT

    @staticmethod
    def _dist(p1, p2): return abs(p1['x'] - p2['x'])

    # ── Blocking (RT-based) ──

    def _enter_block(self, low=False, reason=""):
        """Enter committed block stance using RT."""
        self.blocking = True; self.block_low = low; self.block_timer = 0
        block_auto(self.bwd, low=low)
        return f"BLOCK {'LOW' if low else 'HIGH'} [{reason}]"

    def _maintain_block(self, dist):
        """Hold block with RT. Update high/low from input stream live."""
        self.block_timer += 1

        # Live switch high/low based on opponent's current inputs
        if self.threat.cur_low or self.threat.low_in_last_n(2):
            self.block_low = True
        elif self.threat.cur_attacking:
            self.block_low = False

        block_auto(self.bwd, low=self.block_low)

        # Release conditions — very conservative (matching Kollector)
        if dist > 900:
            self.blocking = False; return None
        if self.block_timer >= 180:
            self.blocking = False; return None

        # Only release when ALL of:
        #   - Held block for 18+ frames
        #   - No damage for 18+ frames
        #   - No opponent attack input for 4+ frames
        #   - Opponent not approaching
        if (self.block_timer >= 18
                and self.threat.frames_since_our_dmg >= 18
                and not self.threat.atk_in_last_n(4)
                and not self.threat.opponent_approaching()):
            self.blocking = False
            return None

        # Still taking damage? Reset timer, try switching high/low
        if self.threat.we_took_damage_recently(frames=3):
            self.block_timer = 0
            self.block_low = not self.block_low

        return "HOLDING BLOCK"

    def _default_guard(self):
        """Default stance: RT + back. ALWAYS blocking when idle."""
        block_stand(self.bwd)

    # ── Main loop ──

    def decide(self, p1, p2):
        self._facing(p1, p2)
        self.threat.update(p1, p2)
        self.mixup.tick()
        dist = self._dist(p1, p2)

        # P1: Committed block
        if self.blocking:
            result = self._maintain_block(dist)
            if result is not None: return result
            self.cd = 0
            return self._punish(dist, p2)

        # P2: Should we block?
        should, is_low, reason = self.threat.should_block(dist)
        if should:
            return self._enter_block(low=is_low, reason=reason)

        if reason == "throw_tech":
            _press([UP], 2); self.cd = 3; return "TECH THROW"

        if reason == "anti_air" and dist < self.MID_DIST:
            combo_d2_antiair(self.fwd, self.bwd)
            self.cd = COOLDOWN["d2_aa"]
            return "D2→DB3A→F3,2→BF1 [AA]"

        # P3: Cooldown — hold RT (blocking while recovering)
        if self.cd > 0:
            self.cd -= 1
            # If opponent attacks during CD → enter committed block
            if self.threat.cur_attacking and dist < self.MID_DIST + 50:
                return self._enter_block(low=self.threat.cur_low, reason="atk_in_cd")
            if self.threat.we_took_damage_recently(6):
                return self._enter_block(low=False, reason="hit_in_cd")
            self._default_guard()  # RT + back while waiting
            return "GUARDING"

        # P4: Fatal
        if not self.fatal_used and p1['hp'] < 0.30 and dist < self.MID_DIST:
            do("FATAL", self.fwd, self.bwd)
            self.fatal_used = True; self.cd = COOLDOWN["fatal"]
            return "FATAL BLOW — GET OVER HERE"

        # P6: Anti-air
        if self.threat.opponent_airborne() and dist < self.MID_DIST:
            combo_d2_antiair(self.fwd, self.bwd)
            self.cd = COOLDOWN["d2_aa"]
            return "D2→DB3A→F3,2→BF1 [AA]"

        # P7: Offense
        if dist > self.FULL_DIST:   return self._off_fullscreen()
        if dist > self.FAR_DIST:    return self._off_far()
        if dist > self.PB_DIST:     return self._off_mid(p1, p2, dist)
        return self._off_pb(p1, p2, dist)

    # ── Offense routines ──

    def _off_fullscreen(self):
        f, b = self.fwd, self.bwd
        r = np.random.random()
        if r < 0.30:
            combo_raw_spear(f, b); self.cd = COOLDOWN["raw_spear"]; return "BF1 Spear [fullscreen]"
        if r < 0.60:
            combo_raw_hellport(f, b); self.cd = COOLDOWN["raw_hp"]; return "DB3 Teleport [fullscreen]"
        if r < 0.80:
            self.mixup.used_teleport()
            combo_raw_hellport_amp(f, b); self.cd = COOLDOWN["raw_hp_amp"]; return "DB3A→COMBO [fullscreen]"
        _press([f, f], 3, 0); _press([f, f], 3, 0)
        self.cd = COOLDOWN["dash"]; return "DASH DASH"

    def _off_far(self):
        f, b = self.fwd, self.bwd
        r = np.random.random()
        if r < 0.25:
            combo_raw_spear(f, b); self.cd = COOLDOWN["raw_spear"]; return "BF1 Spear [far]"
        if r < 0.55:
            self.mixup.used_teleport()
            combo_raw_hellport_amp(f, b); self.cd = COOLDOWN["raw_hp_amp"]; return "DB3A→F3,2→BF1 [teleport combo]"
        if r < 0.70:
            _press([f, f], 3, 0); _press([f, f], 3, 0)
            self.cd = COOLDOWN["dash"]; return "DASH DASH"
        if r < 0.85:
            do("F3", f, b); self.cd = COOLDOWN["f3"]; return "F3 [advance]"
        do("B2", f, b); self.cd = COOLDOWN["b2"]; return "B2 [reach]"

    def _off_mid(self, p1, p2, dist):
        f, b = self.fwd, self.bwd

        # Kill confirm
        if p2['hp'] < 0.18:
            combo_21_hellport_kill(f, b); self.cd = COOLDOWN["21_hp_kill"]
            return "2,1~DB3A→F3,F3,2~BF1A [KILL]"

        # Forced mixups
        if self.mixup.should_force_low():
            self.mixup.used_low()
            combo_f42_hellport_spear(f, b); self.cd = COOLDOWN["f42_hp_spear"]
            return "F4,2~DB3A→F3,F3,2~BF1 [low forced]"
        if self.mixup.should_force_mid():
            self.mixup.used_mid()
            combo_21_hellport_spear(f, b); self.cd = COOLDOWN["21_hp_spear"]
            return "2,1~DB3A→F3,F3,2~BF1 [mid forced]"

        r = np.random.random()
        lw = self.mixup.low_weight()
        mw = self.mixup.mid_weight()

        cuts = np.cumsum([
            0.18,   # 2,1 ~ DB3A full combo
            lw,     # F4,2 low starter combo
            mw,     # B1,4 ~ DB3A combo
            0.12,   # F3,2 ~ DB3A advancing combo
            0.07,   # B1,4,3 safe string
            0.08,   # 2,1,2 ~ BF1 spear
            0.07,   # F3,2 ~ BF1 quick
            0.07,   # Raw teleport amp combo
            0.03,   # F3 advance
            0.03,   # B1 poke
            0.03,   # B2 reach
            0.02,   # D3 low
            0.02,   # D4 low
            0.02,   # D1 poke
            0.01,   # Raw spear
            0.02,   # Throw
        ])
        cuts /= cuts[-1]

        if r < cuts[0]:
            self.mixup.used_mid()
            combo_21_hellport_spear(f, b); self.cd = COOLDOWN["21_hp_spear"]
            return "2,1~DB3A→F3,F3,2~BF1"
        if r < cuts[1]:
            self.mixup.used_low()
            combo_f42_hellport_spear(f, b); self.cd = COOLDOWN["f42_hp_spear"]
            return "F4,2~DB3A→F3,F3,2~BF1 [low]"
        if r < cuts[2]:
            self.mixup.used_low()
            combo_b14_hellport_spear(f, b); self.cd = COOLDOWN["b14_hp_spear"]
            return "B1,4~DB3A→F3,F3,2~BF1"
        if r < cuts[3]:
            self.mixup.used_mid()
            combo_f32_hellport_spear(f, b); self.cd = COOLDOWN["f32_hp_spear"]
            return "F3,2~DB3A→F3,F3,2~BF1"
        if r < cuts[4]:
            combo_b143_standalone(f, b); self.cd = COOLDOWN["b143"]
            return "B1,4,3 [safe string]"
        if r < cuts[5]:
            combo_212_spear(f, b); self.cd = COOLDOWN["212_spear"]
            return "2,1,2~BF1"
        if r < cuts[6]:
            combo_f32_spear(f, b); self.cd = COOLDOWN["f32_spear"]
            return "F3,2~BF1"
        if r < cuts[7]:
            self.mixup.used_teleport()
            combo_raw_hellport_amp(f, b); self.cd = COOLDOWN["raw_hp_amp"]
            return "DB3A→F3,2~BF1 [teleport]"
        if r < cuts[8]:
            do("F3", f, b); self.cd = COOLDOWN["f3"]; return "F3"
        if r < cuts[9]:
            do("B1", f, b); self.cd = COOLDOWN["b1"]; return "B1 [best mid]"
        if r < cuts[10]:
            do("B2", f, b); self.cd = COOLDOWN["b2"]; return "B2 [reach]"
        if r < cuts[11]:
            self.mixup.used_low(); do("D3", f, b); self.cd = COOLDOWN["d3"]; return "D3 [low]"
        if r < cuts[12]:
            self.mixup.used_low(); do("D4", f, b); self.cd = COOLDOWN["d4"]; return "D4 [low]"
        if r < cuts[13]:
            do("D1", f, b); self.cd = COOLDOWN["d1"]; return "D1"
        if r < cuts[14]:
            combo_raw_spear(f, b); self.cd = COOLDOWN["raw_spear"]; return "BF1 Spear"
        if dist < self.THROW_DIST:
            self.mixup.used_throw(); do("THROW_F", f, b); self.cd = COOLDOWN["throw"]; return "Throw"
        _press([self.fwd], 4, 0); self.cd = 1; return "WALK IN"

    def _off_pb(self, p1, p2, dist):
        f, b = self.fwd, self.bwd

        if p2['hp'] < 0.18:
            combo_21_hellport_kill(f, b); self.cd = COOLDOWN["21_hp_kill"]
            return "2,1~DB3A→KILL"

        if self.mixup.should_force_low():
            self.mixup.used_low()
            combo_f42_hellport_spear(f, b); self.cd = COOLDOWN["f42_hp_spear"]
            return "F4,2~DB3A [low shift]"
        if self.mixup.should_force_mid():
            self.mixup.used_mid()
            combo_21_hellport_spear(f, b); self.cd = COOLDOWN["21_hp_spear"]
            return "2,1~DB3A [mid shift]"
        if self.mixup.should_force_throw() and dist < self.THROW_DIST:
            self.mixup.used_throw()
            do("THROW_F" if np.random.random() < 0.5 else "THROW_B", f, b)
            self.cd = COOLDOWN["throw"]; return "Throw [shift]"

        r = np.random.random()
        cuts = np.cumsum([
            0.16,  # 2,1 HP combo
            0.14,  # F4,2 low combo
            0.08,  # B1,4,3 safe
            0.08,  # Throw
            0.04,  # D1 poke
            0.04,  # D4 low
            0.08,  # B1,4 HP combo
            0.07,  # 2,1,2 spear
            0.07,  # F3,2 spear
            0.03,  # D3 low
            0.06,  # 1,1 HP combo
            0.03,  # B1 mid
            0.03,  # B2 reach
            0.04,  # 2,1 spear (quick)
            0.03,  # Back throw
            0.02,  # F3,4 KB string
        ])
        cuts /= cuts[-1]

        if r<cuts[0]:
            self.mixup.used_mid(); combo_21_hellport_spear(f,b); self.cd=COOLDOWN["21_hp_spear"]; return "2,1~DB3A→BF1"
        if r<cuts[1]:
            self.mixup.used_low(); combo_f42_hellport_spear(f,b); self.cd=COOLDOWN["f42_hp_spear"]; return "F4,2~DB3A→BF1 [low]"
        if r<cuts[2]:
            combo_b143_standalone(f,b); self.cd=COOLDOWN["b143"]; return "B1,4,3 [safe]"
        if r<cuts[3] and dist<self.THROW_DIST:
            self.mixup.used_throw(); do("THROW_F",f,b); self.cd=COOLDOWN["throw"]; return "Throw"
        if r<cuts[4]:
            do("D1",f,b); self.cd=COOLDOWN["d1"]; return "D1"
        if r<cuts[5]:
            self.mixup.used_low(); do("D4",f,b); self.cd=COOLDOWN["d4"]; return "D4 [low]"
        if r<cuts[6]:
            self.mixup.used_low(); combo_b14_hellport_spear(f,b); self.cd=COOLDOWN["b14_hp_spear"]; return "B1,4~DB3A→BF1"
        if r<cuts[7]:
            combo_212_spear(f,b); self.cd=COOLDOWN["212_spear"]; return "2,1,2~BF1"
        if r<cuts[8]:
            combo_f32_spear(f,b); self.cd=COOLDOWN["f32_spear"]; return "F3,2~BF1"
        if r<cuts[9]:
            self.mixup.used_low(); do("D3",f,b); self.cd=COOLDOWN["d3"]; return "D3 [low]"
        if r<cuts[10]:
            combo_11_hellport_spear(f,b); self.cd=COOLDOWN["11_hp_spear"]; return "1,1~DB3A→BF1"
        if r<cuts[11]:
            do("B1",f,b); self.cd=COOLDOWN["b1"]; return "B1"
        if r<cuts[12]:
            do("B2",f,b); self.cd=COOLDOWN["b2"]; return "B2"
        if r<cuts[13]:
            combo_21_spear(f,b); self.cd=COOLDOWN["21_spear"]; return "2,1~BF1 [quick]"
        if r<cuts[14] and dist<self.THROW_DIST:
            self.mixup.used_throw(); do("THROW_B",f,b); self.cd=COOLDOWN["throw"]; return "Back Throw"
        # KB string — use sparingly
        self.mixup.used_low(); string_f34(f,b); self.cd=COOLDOWN["f4"]; return "F3,4 [KB string]"

    # ── Punish ──

    def _punish(self, dist, p2):
        f, b = self.fwd, self.bwd

        if p2['hp'] < 0.15 and dist < self.PB_DIST:
            combo_21_hellport_kill(f, b); self.cd = COOLDOWN["21_hp_kill"]
            return "PUNISH: 2,1~DB3A→KILL"

        if dist < self.PB_DIST:
            r = np.random.random()
            if r < 0.35:
                combo_21_hellport_spear(f, b); self.cd = COOLDOWN["21_hp_spear"]
                return "PUNISH: 2,1~DB3A→BF1"
            if r < 0.55:
                combo_13_spear_punish(f, b); self.cd = COOLDOWN["21_spear"]
                return "PUNISH: 2,1~BF1"
            if r < 0.75:
                do("D1", f, b); self.cd = COOLDOWN["d1"]; return "PUNISH: D1"
            combo_b14_spear(f, b); self.cd = COOLDOWN["b14_spear"]
            return "PUNISH: B1,4~BF1"

        if dist < self.MID_DIST:
            r = np.random.random()
            if r < 0.40:
                do("B2", f, b); self.cd = COOLDOWN["b2"]; return "PUNISH: B2"
            if r < 0.70:
                do("F3", f, b); self.cd = COOLDOWN["f3"]; return "PUNISH: F3"
            combo_raw_spear(f, b); self.cd = COOLDOWN["raw_spear"]; return "PUNISH: BF1 Spear"

        # Far — teleport in
        combo_raw_hellport_amp(f, b); self.cd = COOLDOWN["raw_hp_amp"]
        return "PUNISH: DB3A combo"

    def reset(self):
        self.cd = 0; self.blocking = False; self.block_low = False
        self.block_timer = 0; self.fatal_used = False
        self.threat.reset(); self.mixup.reset()


# Helper alias used in punish
def combo_13_spear_punish(f, b):
    combo_21_spear(f, b)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  SCORPION BOT — RT Block + Hyper Aggression")
    print("=" * 70)
    print()
    print("  GET OVER HERE!")
    print("  BLOCK = RT (Right Trigger) — matching Kollector")
    print("  Standing block = RT + BACK")
    print("  Crouching block = RT + DOWN + BACK")
    print("  Between every attack → snap back to RT block")
    print("  Input stream reads: attack/low/throw/jump/special")
    print("  BnB: [Starter] ~ DB3 AMP, F3, F3,2 ~ BF1")
    print()

    vision = VisionEngine()
    vision.start()

    print(">> Waiting for match lock...")
    while not vision.ready:
        time.sleep(0.1)
    print(">> Locked.\n")

    bot  = ScorpionBot()
    tick = time.time()

    try:
        while True:
            elapsed = time.time() - tick
            if elapsed < FRAME: time.sleep(FRAME - elapsed)
            tick = time.time()

            state = vision.get_state()
            if not state: continue

            p1, p2 = state["p1"], state["p2"]
            action = bot.decide(p1, p2)

            if action in ("GUARDING", "HOLDING BLOCK"):
                continue

            dist = abs(p1['x'] - p2['x'])
            opp_inp = inputs_to_str(p2.get('inputs', []))
            print(
                f"Dist:{dist:>5.0f} | "
                f"SCO:{p1['hp']*1000:>4.0f} | "
                f"OPP:{p2['hp']*1000:>4.0f} | "
                f"Inp:{opp_inp:<20} | "
                f"Dmg:{bot.threat.frames_since_our_dmg:>3} | "
                f"BT:{bot.block_timer:>3} | "
                f"CD:{bot.cd:>2} | "
                f"L:{bot.mixup.low_count} M:{bot.mixup.mid_count} "
                f"T:{bot.mixup.throw_count} | "
                f"{action}"
            )

            if p1['hp'] <= 0.01 or p2['hp'] <= 0.01:
                print("\n>> Round over.\n")
                gamepad.reset()
                gamepad.right_trigger(0)
                gamepad.update()
                bot.reset()
                time.sleep(2.5)

    except KeyboardInterrupt:
        print("\n>> Bot offline.")
    finally:
        gamepad.reset()
        gamepad.right_trigger(0)
        gamepad.update()
        vision.running = False
        vision.join()