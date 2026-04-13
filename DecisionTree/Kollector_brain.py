"""
Kollector_brain.py  —  Hyper-Aggressive Kollector with RT Blocking

BLOCKING: MK11 uses RT (Right Trigger) as dedicated block button.
  - Standing block = RT + BACK
  - Crouching block = RT + DOWN + BACK
  - Every frame not attacking → RT is held (always blocking)

AGGRESSION: The bot attacks CONSTANTLY. Short cooldowns, full combos,
relentless pressure. Between every attack → snap back to RT block.
The opponent never gets a turn because:
  1. Bot is always either attacking or blocking
  2. Input stream reads opponent buttons → block before hit lands
  3. After blocking → instant punish with full combo
  4. After combo → immediately back to blocking

DECISION PRIORITY:
  1. Am I in block stance? → maintain or release to punish
  2. Should I block? (input stream + damage + approach) → enter block
  3. Cooldown? → hold RT (blocking while recovering)
  4. Opponent airborne? → D2 anti-air
  5. ATTACK (always, as fast as possible)
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
# GAMEPAD
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
# ATTACK PRIMITIVES — release RT, press attack, return to RT
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
    if gap > 0:
        time.sleep(FRAME * gap)


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
    if gap > 0:
        time.sleep(FRAME * gap)


# ═══════════════════════════════════════════════════════════════════════
# MOVE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════

def do(key, fwd, bwd, gap=0):
    match key:
        # Normals
        case "1":      _press([B1], 2, gap)
        case "2":      _press([B2], 2, gap)
        case "3":      _press([B3], 2, gap)
        case "4":      _press([B4], 2, gap)
        case "F1":     _press([fwd, B1], 2, gap)
        case "F2":     _press([fwd, B2], 2, gap)
        case "F3":     _press([fwd, B3], 2, gap)
        case "F4":     _press([fwd, B4], 2, gap)
        case "B1":     _press([bwd, B1], 2, gap)
        case "B2":     _press([bwd, B2], 2, gap)
        case "B3":     _press([bwd, B3], 2, gap)
        case "B4":     _press([bwd, B4], 2, gap)
        case "D1":     _press([DOWN, B1], 2, gap)
        case "D2":     _press([DOWN, B2], 2, gap)
        case "D3":     _press([DOWN, B3], 2, gap)
        case "D4":     _press([DOWN, B4], 2, gap)
        # Specials
        case "DB3":    _motion([DOWN, bwd], B3, gap)
        case "DB3A":   _motion([DOWN, bwd], B3, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "DBF3":   _motion([DOWN, bwd, fwd], B3, gap)
        case "DF1":    _motion([DOWN, fwd], B1, gap)
        case "DF1F":   _motion([DOWN, fwd], B1, 0); _press([fwd], 2, gap)
        case "BF2":    _motion([bwd, fwd], B2, gap)
        case "BF4":    _motion([bwd, fwd], B4, gap)
        case "BF4A":   _motion([bwd, fwd], B4, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "DB4":    _motion([DOWN, bwd], B4, gap)
        case "DB1":    _motion([DOWN, bwd], B1, gap)
        case "DD3":    _press([DOWN], 2, 1); _press([DOWN, B3], 2, gap)
        case "THROW_F": _press([fwd, B1, B3], 2, gap)
        case "THROW_B": _press([bwd, B1, B3], 2, gap)
        case "FATAL":  _press([LB, RB], 3, gap)
        case _: pass


# ═══════════════════════════════════════════════════════════════════════
# STRINGS — 12 frame gaps
# ═══════════════════════════════════════════════════════════════════════
HIT_GAP = 12
CANCEL_GAP = 4

def string_13(f, b):    _press([B1], 2, HIT_GAP); _press([B3], 2, CANCEL_GAP)
def string_f12(f, b):   _press([f, B1], 2, HIT_GAP); _press([B2], 2, CANCEL_GAP)
def string_b12(f, b):   _press([b, B1], 2, HIT_GAP); _press([B2], 2, CANCEL_GAP)
def string_443(f, b):   _press([B4], 2, HIT_GAP); _press([B4], 2, HIT_GAP); _press([B3], 2, CANCEL_GAP)
def string_b34(f, b):   _press([b, B3], 2, HIT_GAP); _press([B4], 2, CANCEL_GAP)
def string_b43(f, b):   _press([b, B4], 2, HIT_GAP); _press([B3], 2, CANCEL_GAP)
def string_f44(f, b):   _press([f, B4], 2, HIT_GAP); _press([B4], 2, CANCEL_GAP)
def string_212(f, b):   _press([B2], 2, HIT_GAP); _press([B1], 2, HIT_GAP); _press([B2], 2, CANCEL_GAP)

# Juggle enders
def juggle_hop2_db3(f, b):
    _press([UP, B2], 3, 0); time.sleep(FRAME*6); _motion([DOWN, b], B3, 0)
def juggle_hop2_dbf3(f, b):
    _press([UP, B2], 3, 0); time.sleep(FRAME*6); _motion([DOWN, b, f], B3, 0)
def juggle_hop2_db3a(f, b):
    _press([UP, B2], 3, 0); time.sleep(FRAME*6); _motion([DOWN, b], B3, 0)
    time.sleep(FRAME*2); _press([RB], 2, 0)

# Full combos
def combo_ravages(f, b, kill=False):
    string_443(f, b); (juggle_hop2_dbf3 if kill else juggle_hop2_db3)(f, b)
def combo_f12(f, b):     string_f12(f, b); juggle_hop2_db3(f, b)
def combo_f2_oh(f, b):   _press([f, B2], 2, CANCEL_GAP); juggle_hop2_db3(f, b)
def combo_d2_aa(f, b):   _press([DOWN, B2], 2, CANCEL_GAP); juggle_hop2_db3a(f, b)
def combo_b12(f, b):     string_b12(f, b); _motion([DOWN, b], B3, 0)
def combo_13(f, b):      string_13(f, b); _motion([DOWN, b], B3, 0)
def combo_b34(f, b):     string_b34(f, b); _motion([b, f], B4, 0); time.sleep(FRAME*2); _press([RB], 2, 0)
def combo_212(f, b):     string_212(f, b); _motion([DOWN, b], B3, 0)
def combo_f44(f, b):     string_f44(f, b); _motion([DOWN, b], B3, 0)
def combo_b43(f, b):     string_b43(f, b); _motion([DOWN, b, f], B3, 0)


# ═══════════════════════════════════════════════════════════════════════
# COOLDOWNS — AGGRESSIVE (short recovery)
# ═══════════════════════════════════════════════════════════════════════
CD = {
    "ravages": 10, "ravages_kill": 14,
    "f12": 10, "f2_oh": 10, "d2_aa": 8,
    "b12": 8, "combo13": 6, "b34": 10,
    "combo212": 8, "f44": 10, "b43": 8,
    "d1": 2, "d2": 3, "d3": 2, "d4": 2,
    "1": 2, "2": 2, "3": 2, "4": 2,
    "f1": 3, "f2": 3, "f3": 3, "f4": 3,
    "b1": 3, "b2": 2, "b3": 3, "b4": 3,
    "throw": 4, "clutch": 5,
    "bagbomb": 5, "mace": 7, "bola": 5, "vial": 5,
    "teleport": 5, "fatal": 8, "dash": 1,
}


# ═══════════════════════════════════════════════════════════════════════
# INPUT STREAM ANALYZER
# ═══════════════════════════════════════════════════════════════════════

class InputStreamAnalyzer:
    """Reads opponent input stream for blocking and prediction."""

    def __init__(self):
        self.input_history = deque(maxlen=30)
        self.our_hp   = deque([1.0]*20, maxlen=20)
        self.our_x    = deque([0.0]*20, maxlen=20)
        self.opp_x    = deque([0.0]*20, maxlen=20)
        self.opp_y    = deque([0.0]*20, maxlen=20)
        self.opp_hp   = deque([1.0]*20, maxlen=20)

        self.frames_since_our_dmg = 999
        self.last_our_hp = 1.0
        self.last_opp_hp = 1.0
        self.consecutive_dmg = 0
        self.approach_frames = 0

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
            self.consecutive_dmg += 1
        else:
            self.frames_since_our_dmg = min(999, self.frames_since_our_dmg + 1)
            if self.frames_since_our_dmg > 4:
                self.consecutive_dmg = 0
        self.last_our_hp = cur_hp

        opp_hp = p2['hp']
        self.last_opp_hp = opp_hp

        # Approach tracking
        if len(self.opp_x) >= 4:
            ox, ux = list(self.opp_x), list(self.our_x)
            delta = abs(ox[-4]-ux[-4]) - abs(ox[-1]-ux[-1])
            if delta > 3.0:
                self.approach_frames += 1
            else:
                self.approach_frames = max(0, self.approach_frames - 1)

    def atk_in_last_n(self, n=3):
        return any(has_attack(f) for f in list(self.input_history)[-n:])

    def low_in_last_n(self, n=3):
        return any(has_low_attack(f) for f in list(self.input_history)[-n:])

    def jump_in_last_n(self, n=4):
        return any(has_jump_attack(f) for f in list(self.input_history)[-n:])

    def throw_in_last_n(self, n=3):
        return any(has_throw(f) for f in list(self.input_history)[-n:])

    def we_took_damage(self, n=6):
        return self.frames_since_our_dmg <= n

    def being_combod(self):
        return self.consecutive_dmg >= 2

    def opp_airborne(self):
        return max(list(self.opp_y)[-4:]) > 10.0

    def opp_approaching_fast(self):
        return self.approach_frames >= 5

    def opp_blocking(self):
        return self.cur_blocking

    def should_block_low(self):
        """Determine if we should crouch block based on input stream."""
        if self.cur_low:
            return True
        if self.low_in_last_n(3):
            return True
        return False

    def should_block(self, dist):
        """Returns (should_block, is_low, reason)."""
        # Throw tech
        if (self.cur_throw or self.throw_in_last_n(2)) and dist < 180:
            return False, False, "throw_tech"

        # Jump attack → anti-air
        if (self.cur_jump_atk or self.jump_in_last_n(3)) and dist < 400:
            return False, False, "anti_air"

        # Direct input read: face button pressed
        if self.cur_attacking and dist < 420:
            return True, self.cur_low, "input_read"

        # Recent attack in last 3 frames
        if self.atk_in_last_n(3) and dist < 400:
            return True, self.low_in_last_n(3), "recent_atk"

        # Special motion detected
        if self.cur_special and dist < 500:
            return True, False, f"special:{self.cur_special}"

        # Damage — block the string
        if self.we_took_damage(12):
            return True, self.should_block_low(), "damage"

        # Being combod
        if self.being_combod():
            return True, self.should_block_low(), "combo"

        # Opponent rushing in
        if self.opp_approaching_fast() and dist < 350:
            return True, self.should_block_low(), "rush"

        return False, False, ""

    def reset(self):
        self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# MIXUP TRACKER
# ═══════════════════════════════════════════════════════════════════════

class MixupTracker:
    def __init__(self):
        self.low=0; self.oh=0; self.throw=0; self.grab=0; self.n=0
    def tick(self):
        self.n+=1
        if self.n%30==0:
            self.low=max(0,self.low-1); self.oh=max(0,self.oh-1)
            self.throw=max(0,self.throw-1); self.grab=max(0,self.grab-1)
    def reset(self): self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# KOLLECTOR BOT — HYPER AGGRESSIVE
# ═══════════════════════════════════════════════════════════════════════

class KollectorBot:
    THROW_DIST=120; GRAB_DIST=135; PB_DIST=170
    MID_DIST=355; FAR_DIST=520; FULL_DIST=700

    def __init__(self):
        self.cd = 0
        self.blocking = False
        self.block_low = False
        self.block_timer = 0
        self.fwd = RIGHT
        self.bwd = LEFT
        self.fatal_used = False
        self.stream = InputStreamAnalyzer()
        self.mixup = MixupTracker()

    def _facing(self, p1, p2):
        if p1['x'] < p2['x']:
            self.fwd, self.bwd = RIGHT, LEFT
        else:
            self.fwd, self.bwd = LEFT, RIGHT

    @staticmethod
    def _dist(p1, p2):
        return abs(p1['x'] - p2['x'])

    # ── BLOCKING with RT ──────────────────────────────────────────

    def _enter_block(self, low=False, reason=""):
        """Enter committed block stance using RT."""
        self.blocking = True
        self.block_low = low
        self.block_timer = 0
        block_auto(self.bwd, low=low)
        return f"BLOCK {'LOW' if low else 'HIGH'} [{reason}]"

    def _maintain_block(self, dist):
        """Hold block. Update high/low from input stream live."""
        self.block_timer += 1

        # Live switch high/low based on opponent's current inputs
        if self.stream.cur_low or self.stream.low_in_last_n(2):
            self.block_low = True
        elif self.stream.cur_attacking:
            self.block_low = False

        block_auto(self.bwd, low=self.block_low)

        # Release conditions — very conservative
        if dist > 900:
            self.blocking = False; return None
        if self.block_timer >= 180:
            self.blocking = False; return None

        # Only release when ALL of:
        #   - Held block for 30+ frames
        #   - No damage for 30+ frames
        #   - No opponent attack input for 15+ frames
        #   - Opponent not approaching
        if (self.block_timer >= 30
                and self.stream.frames_since_our_dmg >= 30
                and not self.stream.atk_in_last_n(6)
                and not self.stream.opp_approaching_fast()):
            self.blocking = False
            return None

        # Still taking damage? Reset timer, try switching
        if self.stream.we_took_damage(3):
            self.block_timer = 0
            self.block_low = not self.block_low

        return "HOLDING BLOCK"

    def _guard(self):
        """Default stance: RT + back. ALWAYS blocking when idle."""
        block_stand(self.bwd)

    # ── MAIN DECISION ─────────────────────────────────────────────

    def decide(self, p1, p2):
        self._facing(p1, p2)
        self.stream.update(p1, p2)
        self.mixup.tick()
        dist = self._dist(p1, p2)

        # ══════════════════════════════════════════════════════════
        # P1: IN COMMITTED BLOCK → maintain or release to PUNISH
        # ══════════════════════════════════════════════════════════
        if self.blocking:
            r = self._maintain_block(dist)
            if r is not None:
                return r
            # Block released → IMMEDIATELY punish (we know it's safe
            # because release conditions are very strict)
            self.cd = 0
            return self._punish(dist, p2)

        # ══════════════════════════════════════════════════════════
        # P2: SHOULD WE BLOCK? (input stream intelligence)
        # ══════════════════════════════════════════════════════════
        should, is_low, reason = self.stream.should_block(dist)

        if should:
            return self._enter_block(low=is_low, reason=reason)

        if reason == "throw_tech":
            _press([UP], 2)
            self.cd = 2
            return "TECH THROW"

        if reason == "anti_air" and dist < self.MID_DIST:
            combo_d2_aa(self.fwd, self.bwd)
            self.cd = CD["d2_aa"]
            return "D2→JUGGLE [AA]"

        # ══════════════════════════════════════════════════════════
        # P3: COOLDOWN → hold RT (blocking while recovering)
        # ══════════════════════════════════════════════════════════
        if self.cd > 0:
            self.cd -= 1
            # If opponent attacks during CD → enter committed block
            if self.stream.cur_attacking and dist < self.MID_DIST + 50:
                return self._enter_block(low=self.stream.cur_low, reason="atk_in_cd")
            if self.stream.we_took_damage(6):
                return self._enter_block(low=False, reason="hit_in_cd")
            self._guard()  # RT + back while waiting
            return "GUARDING"

        # ══════════════════════════════════════════════════════════
        # P4: FATAL BLOW
        # ══════════════════════════════════════════════════════════
        if not self.fatal_used and p1['hp'] < 0.30 and dist < self.MID_DIST:
            do("FATAL", self.fwd, self.bwd)
            self.fatal_used = True
            self.cd = CD["fatal"]
            return "FATAL BLOW"

        # ══════════════════════════════════════════════════════════
        # P5: ANTI-AIR
        # ══════════════════════════════════════════════════════════
        if self.stream.opp_airborne() and dist < self.MID_DIST:
            combo_d2_aa(self.fwd, self.bwd)
            self.cd = CD["d2_aa"]
            return "D2→JUGGLE [AA]"

        # ══════════════════════════════════════════════════════════
        # P6: OFFENSE — RELENTLESS AGGRESSION
        # No "is_safe_to_attack" gate. If we're not blocking and
        # not in cooldown, we ATTACK. Period.
        # The input-stream block check (P2) protects us.
        # ══════════════════════════════════════════════════════════

        if dist > self.FULL_DIST:
            return self._off_full()
        if dist > self.FAR_DIST:
            return self._off_far()
        if dist > self.PB_DIST:
            return self._off_mid(p1, p2, dist)
        return self._off_pb(p1, p2, dist)

    # ══════════════════════════════════════════════════════════════════
    # OFFENSE — full aggression at every range
    # ══════════════════════════════════════════════════════════════════

    def _off_full(self):
        f, b = self.fwd, self.bwd
        r = np.random.random()
        if r < 0.50:
            do("DD3", f, b); self.cd = CD["teleport"]
            return "TELEPORT IN"
        if r < 0.75:
            _press([f, f], 3, 0); _press([f, f], 3, 0)
            self.cd = CD["dash"]; return "DASH DASH"
        if r < 0.90:
            do("DF1", f, b); self.cd = CD["bagbomb"]
            return "Bag Bomb"
        do("BF2", f, b); self.cd = CD["mace"]
        return "Demonic Mace"

    def _off_far(self):
        f, b = self.fwd, self.bwd
        r = np.random.random()
        if r < 0.40:
            do("DD3", f, b); self.cd = CD["teleport"]
            return "TELEPORT"
        if r < 0.55:
            _press([f, f], 3, 0); _press([f, f], 3, 0)
            self.cd = CD["dash"]; return "DASH DASH"
        if r < 0.70:
            do("DF1", f, b); self.cd = CD["bagbomb"]
            return "Bag Bomb"
        if r < 0.80:
            do("BF2", f, b); self.cd = CD["mace"]
            return "Demonic Mace"
        if r < 0.90:
            do("BF4", f, b); self.cd = CD["bola"]
            return "Damned Bola"
        do("F3", f, b); self.cd = CD["f3"]
        return "F3"

    def _off_mid(self, p1, p2, dist):
        """Mid range: FULL COMBOS. The bot is aggressive — it commits."""
        f, b = self.fwd, self.bwd

        # Kill confirm
        if p2['hp'] < 0.18:
            combo_ravages(f, b, kill=True)
            self.cd = CD["ravages_kill"]
            return "Ravages→CLUTCH [KILL]"

        # Opponent is blocking → throw/grab mixup
        if self.stream.opp_blocking():
            r2 = np.random.random()
            if r2 < 0.4 and dist < self.GRAB_DIST:
                self.mixup.grab += 1
                do("DBF3", f, b); self.cd = CD["clutch"]
                return "Demonic Clutch [opp blocking]"
            if r2 < 0.7 and dist < self.THROW_DIST:
                self.mixup.throw += 1
                do("THROW_F", f, b); self.cd = CD["throw"]
                return "Throw [opp blocking]"

        r = np.random.random()
        lw = max(0.04, 0.16 - self.mixup.low * 0.04)
        ow = max(0.04, 0.14 - self.mixup.oh * 0.04)

        c = np.cumsum([
            0.16,  # Ravages combo
            lw,    # F1,2 low combo
            ow,    # F2 overhead combo
            0.09,  # B1,2 → DB3
            0.07,  # 2,1,2 → DB3
            0.06,  # B3,4 → AmpBola
            0.05,  # F4,4 → DB3
            0.05,  # B4,3 → Clutch
            0.04,  # 1,3 → DB3
            0.04,  # D1 poke
            0.04,  # B2 stagger
            0.03,  # D3 low
            0.03,  # D4 low
            0.03,  # F3
            0.02,  # 4 poke
        ])
        c /= c[-1]

        if r < c[0]:
            combo_ravages(f, b); self.cd = CD["ravages"]
            return "4,4,3→HOP2→DB3"
        if r < c[1]:
            self.mixup.low += 1; combo_f12(f, b); self.cd = CD["f12"]
            return "F1,2→HOP2→DB3 [low]"
        if r < c[2]:
            self.mixup.oh += 1; combo_f2_oh(f, b); self.cd = CD["f2_oh"]
            return "F2→HOP2→DB3 [OH]"
        if r < c[3]:
            combo_b12(f, b); self.cd = CD["b12"]
            return "B1,2→DB3"
        if r < c[4]:
            combo_212(f, b); self.cd = CD["combo212"]
            return "2,1,2→DB3"
        if r < c[5]:
            combo_b34(f, b); self.cd = CD["b34"]
            return "B3,4→AmpBola"
        if r < c[6]:
            combo_f44(f, b); self.cd = CD["f44"]
            return "F4,4→DB3"
        if r < c[7]:
            combo_b43(f, b); self.cd = CD["b43"]
            return "B4,3→Clutch"
        if r < c[8]:
            combo_13(f, b); self.cd = CD["combo13"]
            return "1,3→DB3"
        if r < c[9]:
            do("D1", f, b); self.cd = CD["d1"]
            return "D1"
        if r < c[10]:
            do("B2", f, b); self.cd = CD["b2"]
            return "B2"
        if r < c[11]:
            self.mixup.low += 1; do("D3", f, b); self.cd = CD["d3"]
            return "D3 [low]"
        if r < c[12]:
            self.mixup.low += 1; do("D4", f, b); self.cd = CD["d4"]
            return "D4 [low]"
        if r < c[13]:
            do("F3", f, b); self.cd = CD["f3"]
            return "F3"
        do("4", f, b); self.cd = CD["4"]
        return "4"

    def _off_pb(self, p1, p2, dist):
        """Point blank: maximum pressure, throws, grabs, mixups."""
        f, b = self.fwd, self.bwd

        if p2['hp'] < 0.18:
            combo_ravages(f, b, kill=True)
            self.cd = CD["ravages_kill"]
            return "Ravages→CLUTCH [KILL]"

        # Opponent blocking → break with throw/grab
        if self.stream.opp_blocking():
            r2 = np.random.random()
            if r2 < 0.45 and dist < self.GRAB_DIST:
                self.mixup.grab += 1
                do("DBF3", f, b); self.cd = CD["clutch"]
                return "Demonic Clutch [opp blocking]"
            if r2 < 0.80 and dist < self.THROW_DIST:
                self.mixup.throw += 1
                do("THROW_F" if r2 < 0.6 else "THROW_B", f, b)
                self.cd = CD["throw"]
                return "Throw [opp blocking]"

        # Forced mixup shifts
        if self.mixup.low >= 2:
            self.mixup.oh += 1; self.mixup.low = 0
            combo_f2_oh(f, b); self.cd = CD["f2_oh"]
            return "F2→HOP2→DB3 [OH shift]"
        if self.mixup.oh >= 2:
            self.mixup.low += 1; self.mixup.oh = 0
            do("F1", f, b); self.cd = CD["f1"]
            return "F1 [low shift]"

        r = np.random.random()
        c = np.cumsum([
            0.13,  # OH combo
            0.13,  # Ravages
            0.10,  # F1 low
            0.08,  # Throw
            0.07,  # D1
            0.07,  # D4 low
            0.06,  # Demonic Clutch
            0.06,  # B4,3 → Clutch
            0.06,  # 1,3 → DB3
            0.05,  # B1,2 → DB3
            0.04,  # D3 low
            0.04,  # 2,1,2 → DB3
            0.04,  # F4,4 → DB3
            0.03,  # B2
            0.02,  # Back throw
            0.02,  # F3
        ])
        c /= c[-1]

        if r < c[0]:
            self.mixup.oh += 1; combo_f2_oh(f, b); self.cd = CD["f2_oh"]
            return "F2→HOP2→DB3 [OH]"
        if r < c[1]:
            combo_ravages(f, b); self.cd = CD["ravages"]
            return "4,4,3→HOP2→DB3"
        if r < c[2]:
            self.mixup.low += 1; do("F1", f, b); self.cd = CD["f1"]
            return "F1 [low]"
        if r < c[3] and dist < self.THROW_DIST:
            self.mixup.throw += 1; do("THROW_F", f, b); self.cd = CD["throw"]
            return "Throw"
        if r < c[4]:
            do("D1", f, b); self.cd = CD["d1"]
            return "D1"
        if r < c[5]:
            self.mixup.low += 1; do("D4", f, b); self.cd = CD["d4"]
            return "D4 [low]"
        if r < c[6] and dist < self.GRAB_DIST:
            self.mixup.grab += 1; do("DBF3", f, b); self.cd = CD["clutch"]
            return "Demonic Clutch"
        if r < c[7]:
            combo_b43(f, b); self.cd = CD["b43"]
            return "B4,3→Clutch"
        if r < c[8]:
            combo_13(f, b); self.cd = CD["combo13"]
            return "1,3→DB3"
        if r < c[9]:
            combo_b12(f, b); self.cd = CD["b12"]
            return "B1,2→DB3"
        if r < c[10]:
            self.mixup.low += 1; do("D3", f, b); self.cd = CD["d3"]
            return "D3 [low]"
        if r < c[11]:
            combo_212(f, b); self.cd = CD["combo212"]
            return "2,1,2→DB3"
        if r < c[12]:
            combo_f44(f, b); self.cd = CD["f44"]
            return "F4,4→DB3"
        if r < c[13]:
            do("B2", f, b); self.cd = CD["b2"]
            return "B2"
        if r < c[14] and dist < self.THROW_DIST:
            self.mixup.throw += 1; do("THROW_B", f, b); self.cd = CD["throw"]
            return "Back Throw"
        do("F3", f, b); self.cd = CD["f3"]
        return "F3"

    # ══════════════════════════════════════════════════════════════════
    # PUNISH — after block releases (we know opponent finished)
    # ══════════════════════════════════════════════════════════════════

    def _punish(self, dist, p2):
        f, b = self.fwd, self.bwd

        if p2['hp'] < 0.15 and dist < self.PB_DIST:
            combo_ravages(f, b, kill=True)
            self.cd = CD["ravages_kill"]
            return "PUNISH: Ravages→CLUTCH"

        if dist < self.PB_DIST:
            r = np.random.random()
            if r < 0.35:
                combo_ravages(f, b); self.cd = CD["ravages"]
                return "PUNISH: Ravages→DB3"
            if r < 0.55:
                combo_13(f, b); self.cd = CD["combo13"]
                return "PUNISH: 1,3→DB3"
            if r < 0.75:
                combo_b12(f, b); self.cd = CD["b12"]
                return "PUNISH: B1,2→DB3"
            combo_212(f, b); self.cd = CD["combo212"]
            return "PUNISH: 2,1,2→DB3"

        if dist < self.MID_DIST:
            r = np.random.random()
            if r < 0.5:
                do("F3", f, b); self.cd = CD["f3"]
                return "PUNISH: F3"
            combo_b34(f, b); self.cd = CD["b34"]
            return "PUNISH: B3,4→AmpBola"

        do("DD3", f, b); self.cd = CD["teleport"]
        return "PUNISH: TELEPORT"

    def reset(self):
        self.cd = 0
        self.blocking = False
        self.block_low = False
        self.block_timer = 0
        self.fatal_used = False
        self.stream.reset()
        self.mixup.reset()


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  KOLLECTOR BOT — RT Block + Hyper Aggression")
    print("=" * 70)
    print()
    print("  BLOCK = RT (Right Trigger) — confirmed working")
    print("  Standing block = RT + BACK")
    print("  Crouching block = RT + DOWN + BACK")
    print("  Between every attack → snap back to RT block")
    print("  Input stream reads: attack/low/throw/jump/special")
    print()

    vision = VisionEngine()
    vision.start()

    print(">> Waiting for match lock...")
    while not vision.ready:
        time.sleep(0.1)
    print(">> Locked.\n")

    bot = KollectorBot()
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

            dist = abs(p1['x'] - p2['x'])
            opp_inp = inputs_to_str(p2.get('inputs', []))
            print(
                f"Dist:{dist:>5.0f} | "
                f"KOL:{p1['hp']*1000:>4.0f} | "
                f"OPP:{p2['hp']*1000:>4.0f} | "
                f"Inp:{opp_inp:<20} | "
                f"Dmg:{bot.stream.frames_since_our_dmg:>3} | "
                f"BT:{bot.block_timer:>3} | "
                f"CD:{bot.cd:>2} | "
                f"L:{bot.mixup.low} O:{bot.mixup.oh} | "
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