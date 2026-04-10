"""
noob_saibot_bot.py  —  Block-First Shadow Wraith

NOOB SAIBOT GAMEPLAN:
  Noob is a mid-range zoner who controls space with shadow specials and
  forces a low/mid 50/50 with Shadow Slide (BF4, low) vs Shadow Tackle
  (BF3, mid). His strings cancel into these specials to stay safe or
  extend combos. Shadow Upknee (DB3) is +4 on block — free pressure.

  Completely different from Scorpion's rushdown or Kollector's trap game.
  Noob wants to keep opponents at B3/F4 range, frustrate them into
  jumping (where D2/F3/DB3 anti-airs punish), and mix low/mid from
  cancelled strings.

KEY TOOLS:
  B1,2,1,4 — Main string (Mid, High, Mid, Low). Cancellable.
  B2,1,4   — No Compassion (Mid, High, Low). Good reach.
  2,1,2    — Assassinate (High, High, Mid). Hit confirm.
  F3,3,3   — Reincarnated (Mid, Mid, Mid). Advancing.
  F4,3     — Possessed (Mid, Low). Ranged low mixup.
  B3       — Longest range normal. Poke from safety.
  F4       — Fast long-range mid. Safe poke.

SPECIALS:
  BF1      — Ghost Ball / Spirit Ball (projectile, High)
  BF3      — Shadow Tackle (Mid, advancing, 11f) — the MID option
  BF3 AMP  — Extended tackle, more damage
  BF4      — Shadow Slide (LOW, advancing, 14f) — the LOW option
  BF4 AMP  — Flips opponent, makes slide safe
  DB3      — Shadow Upknee (Mid, 16f, +4 ON BLOCK) — anti-air, pressure
  DB4      — Teleport (crosses up, 27f)

50/50 MIXUP:
  [String] ~ BF3 (mid)  OR  [String] ~ BF4 (low)
  Opponent must guess. Both are cancellable from B1,2,1,4 and B2,1,4.

COMBO ROUTES:
  F3 (launcher) → dash → 2,1,2 ~ BF3/BF1
  D2 (anti-air KB) → dash → 2,1,2 ~ BF1
  B1,2,1,4 ~ BF4 AMP (safe pressure)
  2,1 ~ DB3 (upknee, +4 on block for continued pressure)
"""

import time
import numpy as np
import vgamepad as vg
from collections import deque
from DMA import VisionEngine

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
B1    = BTN.XUSB_GAMEPAD_X
B2    = BTN.XUSB_GAMEPAD_Y
B3    = BTN.XUSB_GAMEPAD_A
B4    = BTN.XUSB_GAMEPAD_B
LB    = BTN.XUSB_GAMEPAD_LEFT_SHOULDER
RB    = BTN.XUSB_GAMEPAD_RIGHT_SHOULDER

INP_DOWN = 2
INP_ATK  = 64 | 16 | 32 | 128
INP_THRW = 4096

def inp_any_attack(m):  return bool(m & INP_ATK)
def inp_low_atk(m):     return bool(m & INP_DOWN) and bool(m & INP_ATK)
def inp_throw(m):       return bool(m & INP_THRW)


# ═══════════════════════════════════════════════════════════════════════
# PRIMITIVES
# ═══════════════════════════════════════════════════════════════════════
def _press(btns, hold=2, gap=0):
    gamepad.reset()
    for b in btns:
        if b: gamepad.press_button(b)
    gamepad.update()
    time.sleep(FRAME * max(1, hold))
    gamepad.reset(); gamepad.update()
    if gap > 0: time.sleep(FRAME * gap)

def _hold_back(bwd, low=False):
    gamepad.reset()
    if low: gamepad.press_button(DOWN)
    gamepad.press_button(bwd)
    gamepad.update()

def _release():
    gamepad.reset(); gamepad.update()

def _motion(dirs, btn, gap=0):
    for d in dirs:
        gamepad.reset()
        if d: gamepad.press_button(d)
        gamepad.update()
        time.sleep(FRAME * 2)
    gamepad.reset()
    if btn: gamepad.press_button(btn)
    gamepad.update()
    time.sleep(FRAME * 2)
    gamepad.reset(); gamepad.update()
    if gap > 0: time.sleep(FRAME * gap)


# ═══════════════════════════════════════════════════════════════════════
# MOVE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════
def do(key, fwd, bwd, gap=0):
    match key:
        # ── Normals ──
        case "1":      _press([B1], 2, gap)           # Heavy Knuckles — High, 11f
        case "2":      _press([B2], 2, gap)           # Straight Fist — High, 9f
        case "3":      _press([B3], 2, gap)           # Straight Kick — Mid, 26f (slow)
        case "4":      _press([B4], 2, gap)           # Dark Heel — High, 18f
        case "F3":     _press([fwd, B3], 2, gap)      # High Kick — Mid, 17f, LAUNCHER
        case "F4":     _press([fwd, B4], 2, gap)      # Sneaky Saibot — Mid, 22f, range
        case "B1":     _press([bwd, B1], 2, gap)      # Shadow Poke — Mid, 21f, string start
        case "B2":     _press([bwd, B2], 2, gap)      # Dark Push — Mid, 19f, armor break
        case "B3":     _press([bwd, B3], 2, gap)      # Shadow Slice — Mid, LONGEST RANGE
        case "B4":     _press([bwd, B4], 2, gap)      # Sickle Sweep — Low, 22f
        case "D1":     _press([DOWN, B1], 2, gap)     # Knee Hook — Mid, 8f
        case "D2":     _press([DOWN, B2], 2, gap)     # Rising Sickle — Mid, 10f, anti-air KB
        case "D3":     _press([DOWN, B3], 2, gap)     # Boot Slide — Low, 7f fastest
        case "D4":     _press([DOWN, B4], 2, gap)     # Sickle Strike — Low, 12f
        # ── Specials ──
        case "BF1":    _motion([bwd, fwd], B1, gap)   # Ghost Ball — projectile
        case "BF1A":                                    # Amp Ghost Ball
            _motion([bwd, fwd], B1, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "BF3":    _motion([bwd, fwd], B3, gap)   # Shadow Tackle — MID, advancing
        case "BF3A":                                    # Amp Shadow Tackle
            _motion([bwd, fwd], B3, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "BF4":    _motion([bwd, fwd], B4, gap)   # Shadow Slide — LOW, advancing
        case "BF4A":                                    # Amp Shadow Slide — SAFE
            _motion([bwd, fwd], B4, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "DB3":    _motion([DOWN, bwd], B3, gap)  # Shadow Upknee — Mid, +4 on block!
        case "DB3A":                                    # Amp Upknee
            _motion([DOWN, bwd], B3, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "DB4":    _motion([DOWN, bwd], B4, gap)  # Teleport Slam — crosses up
        case "DB4A":                                    # Amp Teleport
            _motion([DOWN, bwd], B4, 0); time.sleep(FRAME*2); _press([RB], 2, gap)
        case "DF2":    _motion([DOWN, fwd], B2, gap)  # Shadow Portal (ability) — combo extend
        # ── Throws ──
        case "THROW_F": _press([fwd, B1, B3], 2, gap)
        case "THROW_B": _press([bwd, B1, B3], 2, gap)
        # ── Fatal ──
        case "FATAL":  _press([LB, RB], 3, gap)
        case _: pass


# ═══════════════════════════════════════════════════════════════════════
# STRINGS
# ═══════════════════════════════════════════════════════════════════════
HIT_GAP = 12
CANCEL_GAP = 4

def string_12(f, b):
    """1,2 — Saibot Blast. High, High. Cancellable."""
    _press([B1], 2, HIT_GAP); _press([B2], 2, CANCEL_GAP)

def string_21(f, b):
    """2,1 — Hit confirm. High, High. Cancel into upknee for pressure."""
    _press([B2], 2, HIT_GAP); _press([B1], 2, CANCEL_GAP)

def string_212(f, b):
    """2,1,2 — Assassinate. High, High, Mid. -7 on block."""
    _press([B2], 2, HIT_GAP); _press([B1], 2, HIT_GAP)
    _press([B2], 2, CANCEL_GAP)

def string_b1214(f, b):
    """B1,2,1,4 — Evil Twin. Mid, High, Mid, Low. Main string.
    Cancel last hit into special. -17 raw (unsafe), cancel to be safe."""
    _press([b, B1], 2, HIT_GAP); _press([B2], 2, HIT_GAP)
    _press([B1], 2, HIT_GAP); _press([B4], 2, CANCEL_GAP)

def string_b12f4(f, b):
    """B1,2,F4 — Sneaky Saibot. Mid, High, Mid. -4 on hit, safe at range."""
    _press([b, B1], 2, HIT_GAP); _press([B2], 2, HIT_GAP)
    _press([f, B4], 2, CANCEL_GAP)

def string_b214(f, b):
    """B2,1,4 — No Compassion. Mid, High, Low. Great reach."""
    _press([b, B2], 2, HIT_GAP); _press([B1], 2, HIT_GAP)
    _press([B4], 2, CANCEL_GAP)

def string_f333(f, b):
    """F3,3,3 — Reincarnated. Mid, Mid, Mid. Advancing."""
    _press([f, B3], 2, HIT_GAP); _press([B3], 2, HIT_GAP)
    _press([B3], 2, CANCEL_GAP)

def string_f43(f, b):
    """F4,3 — Possessed. Mid, Low. 18f total. Low ender."""
    _press([f, B4], 2, HIT_GAP); _press([B3], 2, CANCEL_GAP)


# ═══════════════════════════════════════════════════════════════════════
# COMBO ROUTES
# ═══════════════════════════════════════════════════════════════════════

# ── 50/50 cancels (string into slide vs tackle) ──

def combo_b1214_slide(f, b):
    """B1,2,1,4 ~ BF4 (low). Low 50/50 option."""
    string_b1214(f, b); _motion([b, f], B4, 0)

def combo_b1214_slide_amp(f, b):
    """B1,2,1,4 ~ BF4 AMP. Safe low option."""
    string_b1214(f, b); _motion([b, f], B4, 0)
    time.sleep(FRAME*2); _press([RB], 2, 0)

def combo_b1214_tackle(f, b):
    """B1,2,1,4 ~ BF3 (mid). Mid 50/50 option."""
    string_b1214(f, b); _motion([b, f], B3, 0)

def combo_b1214_tackle_amp(f, b):
    """B1,2,1,4 ~ BF3 AMP. Mid with extra damage."""
    string_b1214(f, b); _motion([b, f], B3, 0)
    time.sleep(FRAME*2); _press([RB], 2, 0)

def combo_b1214_upknee(f, b):
    """B1,2,1,4 ~ DB3. String into +4 upknee. Continued pressure."""
    string_b1214(f, b); _motion([DOWN, b], B3, 0)

def combo_b1214_ghostball(f, b):
    """B1,2,1,4 ~ BF1. String into projectile. Fullscreen pushback."""
    string_b1214(f, b); _motion([b, f], B1, 0)

def combo_b214_slide(f, b):
    """B2,1,4 ~ BF4. Reach string into low."""
    string_b214(f, b); _motion([b, f], B4, 0)

def combo_b214_tackle(f, b):
    """B2,1,4 ~ BF3. Reach string into mid."""
    string_b214(f, b); _motion([b, f], B3, 0)

def combo_b214_upknee(f, b):
    """B2,1,4 ~ DB3. Reach string into +4."""
    string_b214(f, b); _motion([DOWN, b], B3, 0)

def combo_212_tackle(f, b):
    """2,1,2 ~ BF3. Hit confirm into tackle."""
    string_212(f, b); _motion([b, f], B3, 0)

def combo_212_slide(f, b):
    """2,1,2 ~ BF4. Hit confirm into slide."""
    string_212(f, b); _motion([b, f], B4, 0)

def combo_212_ghostball(f, b):
    """2,1,2 ~ BF1. Hit confirm into projectile knockdown."""
    string_212(f, b); _motion([b, f], B1, 0)

def combo_21_upknee(f, b):
    """2,1 ~ DB3. Quick string into +4 pressure."""
    string_21(f, b); _motion([DOWN, b], B3, 0)

def combo_f333_slide(f, b):
    """F3,3,3 ~ BF4. Advancing into low."""
    string_f333(f, b); _motion([b, f], B4, 0)

def combo_f333_tackle(f, b):
    """F3,3,3 ~ BF3. Advancing into mid."""
    string_f333(f, b); _motion([b, f], B3, 0)

# ── Launcher combos ──

def combo_f3_launch(f, b):
    """F3 (launcher) → dash → 2,1,2 ~ BF1. Anti-air / juggle."""
    _press([f, B3], 2, 4)
    _press([f, f], 3, 2)  # dash
    string_212(f, b)
    _motion([b, f], B1, 0)

def combo_f3_launch_tackle(f, b):
    """F3 (launcher) → dash → 2,1,2 ~ BF3. Juggle into tackle."""
    _press([f, B3], 2, 4)
    _press([f, f], 3, 2)
    string_212(f, b)
    _motion([b, f], B3, 0)

def combo_d2_antiair(f, b):
    """D2 (anti-air KB) → dash → 2,1,2 ~ BF1. Full AA combo."""
    _press([DOWN, B2], 2, 4)
    _press([f, f], 3, 2)
    string_212(f, b)
    _motion([b, f], B1, 0)

def combo_d2_antiair_tackle(f, b):
    """D2 → dash → 2,1,2 ~ BF3."""
    _press([DOWN, B2], 2, 4)
    _press([f, f], 3, 2)
    string_212(f, b)
    _motion([b, f], B3, 0)

# ── Quick cancels ──

def combo_21_ghostball(f, b):
    """2,1 ~ BF1. Quick confirm into knockdown."""
    string_21(f, b); _motion([b, f], B1, 0)

def combo_12_slide(f, b):
    """1,2 ~ BF4. Fast string into low."""
    string_12(f, b); _motion([b, f], B4, 0)

def combo_12_tackle(f, b):
    """1,2 ~ BF3. Fast string into mid."""
    string_12(f, b); _motion([b, f], B3, 0)

def combo_f43_upknee(f, b):
    """F4,3 ~ DB3. Ranged low into +4."""
    string_f43(f, b); _motion([DOWN, b], B3, 0)

def combo_raw_slide(f, b):
    """Standalone BF4. Low from range."""
    _motion([b, f], B4, 0)

def combo_raw_slide_amp(f, b):
    """BF4 AMP. Safe low."""
    _motion([b, f], B4, 0); time.sleep(FRAME*2); _press([RB], 2, 0)

def combo_raw_tackle(f, b):
    """Standalone BF3. Mid from range."""
    _motion([b, f], B3, 0)

def combo_raw_ghostball(f, b):
    """Standalone BF1. Zoning projectile."""
    _motion([b, f], B1, 0)

def combo_raw_upknee(f, b):
    """Standalone DB3. Anti-air, +4 on block."""
    _motion([DOWN, b], B3, 0)

def combo_raw_teleport(f, b):
    """Standalone DB4. Crosses up."""
    _motion([DOWN, b], B4, 0)


# ═══════════════════════════════════════════════════════════════════════
# COOLDOWNS
# ═══════════════════════════════════════════════════════════════════════
COOLDOWN = {
    # String combos
    "b1214_slide": 14, "b1214_slide_amp": 16, "b1214_tackle": 14,
    "b1214_tackle_amp": 16, "b1214_upknee": 12, "b1214_ghost": 14,
    "b214_slide": 14, "b214_tackle": 14, "b214_upknee": 12,
    "212_tackle": 12, "212_slide": 12, "212_ghost": 12,
    "21_upknee": 10, "21_ghost": 10,
    "f333_slide": 14, "f333_tackle": 14,
    "f43_upknee": 12,
    "12_slide": 10, "12_tackle": 10,
    # Launcher combos
    "f3_launch": 18, "f3_launch_tackle": 18,
    "d2_aa": 16, "d2_aa_tackle": 16,
    # Raw specials
    "raw_slide": 8, "raw_slide_amp": 10,
    "raw_tackle": 8, "raw_ghost": 8,
    "raw_upknee": 6, "raw_teleport": 8,
    # Pokes
    "d1": 3, "d2": 5, "d3": 3, "d4": 3,
    "1": 3, "2": 3, "b1": 4, "b2": 5,
    "b3": 5, "b4": 5, "f3": 5, "f4": 5,
    # Utility
    "throw": 6, "fatal": 12, "dash": 2,
    "b143_safe": 10, "b12f4": 10,
}


# ═══════════════════════════════════════════════════════════════════════
# THREAT DETECTOR (same as Kollector/Scorpion)
# ═══════════════════════════════════════════════════════════════════════
class ThreatDetector:
    HISTORY_LEN = 30
    def __init__(self):
        self.our_hp=deque([1.0]*self.HISTORY_LEN,maxlen=self.HISTORY_LEN)
        self.our_x=deque([0.0]*self.HISTORY_LEN,maxlen=self.HISTORY_LEN)
        self.opp_x=deque([0.0]*self.HISTORY_LEN,maxlen=self.HISTORY_LEN)
        self.opp_y=deque([0.0]*self.HISTORY_LEN,maxlen=self.HISTORY_LEN)
        self.opp_hp=deque([1.0]*self.HISTORY_LEN,maxlen=self.HISTORY_LEN)
        self.opp_inputs=deque([0]*self.HISTORY_LEN,maxlen=self.HISTORY_LEN)
        self.frames_since_our_dmg=999; self.frames_since_opp_dmg=999
        self.last_our_hp=1.0; self.last_opp_hp=1.0
        self.consecutive_dmg_frames=0
        self.opp_approach_frames=0; self.opp_retreat_frames=0

    def update(self, p1, p2):
        self.our_hp.append(p1['hp']); self.our_x.append(p1['x'])
        self.opp_x.append(p2['x']); self.opp_y.append(p2['y'])
        self.opp_hp.append(p2['hp']); self.opp_inputs.append(p2.get('inputs',0))
        cur=p1['hp']
        if cur<self.last_our_hp-0.002:
            self.frames_since_our_dmg=0; self.consecutive_dmg_frames+=1
        else:
            if self.frames_since_our_dmg<999: self.frames_since_our_dmg+=1
            if self.frames_since_our_dmg>4: self.consecutive_dmg_frames=0
        self.last_our_hp=cur
        ohp=p2['hp']
        if ohp<self.last_opp_hp-0.002: self.frames_since_opp_dmg=0
        else:
            if self.frames_since_opp_dmg<999: self.frames_since_opp_dmg+=1
        self.last_opp_hp=ohp
        if len(self.opp_x)>=4:
            ox,ux=list(self.opp_x),list(self.our_x)
            d=abs(ox[-4]-ux[-4])-abs(ox[-1]-ux[-1])
            if d>3: self.opp_approach_frames+=1; self.opp_retreat_frames=0
            elif d<-2: self.opp_retreat_frames+=1; self.opp_approach_frames=0
            else:
                self.opp_approach_frames=max(0,self.opp_approach_frames-1)
                self.opp_retreat_frames=max(0,self.opp_retreat_frames-1)

    def we_took_damage_recently(self,f=6): return self.frames_since_our_dmg<=f
    def we_are_being_combod(self): return self.consecutive_dmg_frames>=2
    def our_hp_is_stable(self,f=20): return self.frames_since_our_dmg>=f
    def opponent_approaching(self): return self.opp_approach_frames>=3
    def opponent_rushing(self):
        if len(self.opp_x)<4: return False
        ox,ux=list(self.opp_x),list(self.our_x)
        return abs(ox[-4]-ux[-4])-abs(ox[-1]-ux[-1])>12.0
    def opponent_airborne(self): return max(list(self.opp_y)[-4:])>20.0
    def opponent_grounded_approaching(self): return self.opponent_approaching() and not self.opponent_airborne()
    def raw_input_attack(self): return any(inp_any_attack(m) for m in list(self.opp_inputs)[-3:])
    def raw_input_low(self): return any(inp_low_atk(m) for m in list(self.opp_inputs)[-3:])
    def raw_input_throw(self): return any(inp_throw(m) for m in list(self.opp_inputs)[-3:])
    def is_safe_to_attack(self):
        if self.we_took_damage_recently(8): return False
        if self.we_are_being_combod(): return False
        if self.opponent_rushing(): return False
        return True
    def should_block(self, dist):
        if self.we_took_damage_recently(6): return True, self.raw_input_low(), "damage"
        if self.we_are_being_combod(): return True, self.raw_input_low(), "combo"
        if self.opponent_rushing() and dist<450: return True, self.raw_input_low(), "rush"
        if self.opponent_grounded_approaching() and dist<350: return True, self.raw_input_low(), "approach"
        if self.raw_input_attack() and dist<400: return True, self.raw_input_low(), "input"
        if self.raw_input_throw() and dist<180: return False, False, "throw_tech"
        return False, False, ""
    def reset(self): self.__init__()


class MixupTracker:
    def __init__(self):
        self.slide_count=0; self.tackle_count=0
        self.throw_count=0; self.tick_counter=0
    def tick(self):
        self.tick_counter+=1
        if self.tick_counter%40==0:
            self.slide_count=max(0,self.slide_count-1)
            self.tackle_count=max(0,self.tackle_count-1)
            self.throw_count=max(0,self.throw_count-1)
    def used_slide(self): self.slide_count+=1
    def used_tackle(self): self.tackle_count+=1
    def used_throw(self): self.throw_count+=1
    def should_force_slide(self): return self.tackle_count>=2
    def should_force_tackle(self): return self.slide_count>=2
    def should_force_throw(self): return (self.slide_count+self.tackle_count)>=3 and self.throw_count<2
    def slide_weight(self): return max(0.04, 0.16-self.slide_count*0.04)
    def tackle_weight(self): return max(0.04, 0.14-self.tackle_count*0.04)
    def reset(self): self.__init__()


# ═══════════════════════════════════════════════════════════════════════
# NOOB SAIBOT BOT
# ═══════════════════════════════════════════════════════════════════════
class NoobSaibotBot:
    THROW_DIST=120; PB_DIST=170; MID_DIST=355
    FAR_DIST=520; FULL_DIST=700

    def __init__(self):
        self.cd=0; self.blocking=False; self.block_low=False
        self.block_timer=0; self.fwd=RIGHT; self.bwd=LEFT
        self.fatal_used=False
        self.threat=ThreatDetector(); self.mixup=MixupTracker()

    def _facing(self,p1,p2):
        if p1['x']<p2['x']: self.fwd,self.bwd=RIGHT,LEFT
        else: self.fwd,self.bwd=LEFT,RIGHT

    @staticmethod
    def _dist(p1,p2): return abs(p1['x']-p2['x'])

    def _enter_block(self,low=False,reason=""):
        self.blocking=True; self.block_low=low; self.block_timer=0
        _hold_back(self.bwd,low=low)
        return f"BLOCK {'LOW' if low else 'HIGH'} [{reason}]"

    def _maintain_block(self,dist):
        self.block_timer+=1
        if self.threat.raw_input_low(): self.block_low=True
        elif self.threat.raw_input_attack(): self.block_low=False
        _hold_back(self.bwd,low=self.block_low)
        if dist>self.MID_DIST+120: self.blocking=False; return None
        if self.block_timer>=120: self.blocking=False; return None
        if (self.block_timer>=12 and self.threat.our_hp_is_stable(20)
                and not self.threat.opponent_approaching()
                and not self.threat.raw_input_attack()):
            self.blocking=False; return None
        if self.threat.we_took_damage_recently(3):
            self.block_timer=0; self.block_low=not self.block_low
        return "HOLDING BLOCK"

    def _default_guard(self): _hold_back(self.bwd)

    def decide(self,p1,p2):
        self._facing(p1,p2); self.threat.update(p1,p2); self.mixup.tick()
        dist=self._dist(p1,p2)

        if self.blocking:
            r=self._maintain_block(dist)
            if r is not None: return r
            self.cd=0; return self._punish(dist,p2)

        should,is_low,reason=self.threat.should_block(dist)
        if should:
            if reason=="throw_tech": _press([UP],2); self.cd=3; return "TECH THROW"
            return self._enter_block(low=is_low,reason=reason)

        if self.cd>0: self.cd-=1; self._default_guard(); return "GUARDING"
        if not self.threat.is_safe_to_attack(): self._default_guard(); return "GUARDING [not safe]"

        if not self.fatal_used and p1['hp']<0.30 and dist<self.MID_DIST:
            do("FATAL",self.fwd,self.bwd); self.fatal_used=True
            self.cd=COOLDOWN["fatal"]; return "FATAL BLOW"

        if self.threat.opponent_airborne() and dist<self.MID_DIST:
            combo_d2_antiair(self.fwd,self.bwd)
            self.cd=COOLDOWN["d2_aa"]; return "D2→212→BF1 [AA]"

        if dist>self.FULL_DIST: return self._off_full()
        if dist>self.FAR_DIST: return self._off_far()
        if dist>self.PB_DIST: return self._off_mid(p1,p2,dist)
        return self._off_pb(p1,p2,dist)

    # ── FULLSCREEN: zone with Ghost Ball, slide, teleport ──
    def _off_full(self):
        f,b=self.fwd,self.bwd; r=np.random.random()
        if r<0.40: combo_raw_ghostball(f,b); self.cd=COOLDOWN["raw_ghost"]; return "BF1 Ghost Ball [zone]"
        if r<0.60: combo_raw_slide(f,b); self.cd=COOLDOWN["raw_slide"]; return "BF4 Slide [fullscreen low]"
        if r<0.75: combo_raw_tackle(f,b); self.cd=COOLDOWN["raw_tackle"]; return "BF3 Tackle [fullscreen mid]"
        if r<0.90:
            _press([f,f],3,0); _press([f,f],3,0)
            self.cd=COOLDOWN["dash"]; return "DASH DASH"
        combo_raw_teleport(f,b); self.cd=COOLDOWN["raw_teleport"]; return "DB4 Teleport"

    # ── FAR: Ghost Ball zoning, slide/tackle from range ──
    def _off_far(self):
        f,b=self.fwd,self.bwd; r=np.random.random()
        if r<0.30: combo_raw_ghostball(f,b); self.cd=COOLDOWN["raw_ghost"]; return "BF1 Ghost Ball"
        if r<0.45:
            self.mixup.used_slide()
            combo_raw_slide_amp(f,b); self.cd=COOLDOWN["raw_slide_amp"]; return "BF4A Slide AMP [safe low]"
        if r<0.60:
            self.mixup.used_tackle()
            combo_raw_tackle(f,b); self.cd=COOLDOWN["raw_tackle"]; return "BF3 Tackle [mid]"
        if r<0.75:
            do("B3",f,b); self.cd=COOLDOWN["b3"]; return "B3 [longest range]"
        if r<0.85:
            do("F4",f,b); self.cd=COOLDOWN["f4"]; return "F4 [range mid]"
        _press([f,f],3,0); _press([f,f],3,0)
        self.cd=COOLDOWN["dash"]; return "DASH DASH"

    # ── MID: Noob's sweet spot. B1214 pressure, 50/50 cancels ──
    def _off_mid(self,p1,p2,dist):
        f,b=self.fwd,self.bwd

        if p2['hp']<0.18:
            combo_f3_launch(f,b); self.cd=COOLDOWN["f3_launch"]
            return "F3→212→BF1 [KILL]"

        if self.mixup.should_force_slide():
            self.mixup.used_slide()
            combo_b1214_slide_amp(f,b); self.cd=COOLDOWN["b1214_slide_amp"]
            return "B1214~BF4A [slide forced]"
        if self.mixup.should_force_tackle():
            self.mixup.used_tackle()
            combo_b1214_tackle(f,b); self.cd=COOLDOWN["b1214_tackle"]
            return "B1214~BF3 [tackle forced]"

        r=np.random.random()
        sw=self.mixup.slide_weight(); tw=self.mixup.tackle_weight()
        cuts=np.cumsum([
            sw,    # B1214 ~ slide (low 50/50)
            tw,    # B1214 ~ tackle (mid 50/50)
            0.10,  # B1214 ~ upknee (+4 pressure)
            0.08,  # 212 ~ ghostball
            0.07,  # B214 ~ slide (reach low)
            0.06,  # B214 ~ tackle (reach mid)
            0.06,  # F333 ~ slide (advancing low)
            0.05,  # 21 ~ upknee (quick +4)
            0.05,  # F3 launcher combo
            0.04,  # B3 poke
            0.04,  # F4 poke
            0.04,  # D3 low
            0.03,  # D4 low
            0.03,  # D1 poke
            0.03,  # Raw Ghost Ball
            0.02,  # Throw
        ])
        cuts/=cuts[-1]

        if r<cuts[0]:
            self.mixup.used_slide(); combo_b1214_slide_amp(f,b)
            self.cd=COOLDOWN["b1214_slide_amp"]; return "B1214~BF4A [low]"
        if r<cuts[1]:
            self.mixup.used_tackle(); combo_b1214_tackle(f,b)
            self.cd=COOLDOWN["b1214_tackle"]; return "B1214~BF3 [mid]"
        if r<cuts[2]:
            combo_b1214_upknee(f,b); self.cd=COOLDOWN["b1214_upknee"]; return "B1214~DB3 [+4]"
        if r<cuts[3]:
            combo_212_ghostball(f,b); self.cd=COOLDOWN["212_ghost"]; return "212~BF1"
        if r<cuts[4]:
            self.mixup.used_slide(); combo_b214_slide(f,b)
            self.cd=COOLDOWN["b214_slide"]; return "B214~BF4 [low]"
        if r<cuts[5]:
            self.mixup.used_tackle(); combo_b214_tackle(f,b)
            self.cd=COOLDOWN["b214_tackle"]; return "B214~BF3 [mid]"
        if r<cuts[6]:
            self.mixup.used_slide(); combo_f333_slide(f,b)
            self.cd=COOLDOWN["f333_slide"]; return "F333~BF4 [advance low]"
        if r<cuts[7]:
            combo_21_upknee(f,b); self.cd=COOLDOWN["21_upknee"]; return "21~DB3 [+4]"
        if r<cuts[8]:
            combo_f3_launch(f,b); self.cd=COOLDOWN["f3_launch"]; return "F3→212→BF1 [launch]"
        if r<cuts[9]:
            do("B3",f,b); self.cd=COOLDOWN["b3"]; return "B3"
        if r<cuts[10]:
            do("F4",f,b); self.cd=COOLDOWN["f4"]; return "F4"
        if r<cuts[11]:
            do("D3",f,b); self.cd=COOLDOWN["d3"]; return "D3 [low]"
        if r<cuts[12]:
            do("D4",f,b); self.cd=COOLDOWN["d4"]; return "D4 [low]"
        if r<cuts[13]:
            do("D1",f,b); self.cd=COOLDOWN["d1"]; return "D1"
        if r<cuts[14]:
            combo_raw_ghostball(f,b); self.cd=COOLDOWN["raw_ghost"]; return "BF1 Ghost Ball"
        if dist<self.THROW_DIST:
            self.mixup.used_throw(); do("THROW_F",f,b)
            self.cd=COOLDOWN["throw"]; return "Throw"
        _press([self.fwd],4,0); self.cd=1; return "WALK IN"

    # ── POINT BLANK: upknee pressure, 50/50, throws ──
    def _off_pb(self,p1,p2,dist):
        f,b=self.fwd,self.bwd

        if p2['hp']<0.18:
            combo_f3_launch(f,b); self.cd=COOLDOWN["f3_launch"]
            return "F3→212→BF1 [KILL]"

        if self.mixup.should_force_slide():
            self.mixup.used_slide(); combo_b1214_slide_amp(f,b)
            self.cd=COOLDOWN["b1214_slide_amp"]; return "B1214~BF4A [slide shift]"
        if self.mixup.should_force_tackle():
            self.mixup.used_tackle(); combo_b1214_tackle(f,b)
            self.cd=COOLDOWN["b1214_tackle"]; return "B1214~BF3 [tackle shift]"
        if self.mixup.should_force_throw() and dist<self.THROW_DIST:
            self.mixup.used_throw()
            do("THROW_F" if np.random.random()<0.5 else "THROW_B",f,b)
            self.cd=COOLDOWN["throw"]; return "Throw [shift]"

        r=np.random.random()
        cuts=np.cumsum([
            0.12,  # B1214 slide (low)
            0.12,  # B1214 tackle (mid)
            0.10,  # 21 upknee (+4 pressure)
            0.08,  # Throw
            0.07,  # D1 poke
            0.07,  # D3 low
            0.06,  # B1214 upknee
            0.06,  # 212 tackle
            0.06,  # 12 slide (fast low)
            0.05,  # F43 upknee (range low +4)
            0.04,  # D4 low
            0.04,  # B2 armor break
            0.04,  # 212 ghostball
            0.03,  # B214 slide
            0.03,  # Back throw
            0.03,  # B1214 ghostball (pushback)
        ])
        cuts/=cuts[-1]

        if r<cuts[0]:
            self.mixup.used_slide(); combo_b1214_slide_amp(f,b)
            self.cd=COOLDOWN["b1214_slide_amp"]; return "B1214~BF4A [low]"
        if r<cuts[1]:
            self.mixup.used_tackle(); combo_b1214_tackle(f,b)
            self.cd=COOLDOWN["b1214_tackle"]; return "B1214~BF3 [mid]"
        if r<cuts[2]:
            combo_21_upknee(f,b); self.cd=COOLDOWN["21_upknee"]; return "21~DB3 [+4]"
        if r<cuts[3] and dist<self.THROW_DIST:
            self.mixup.used_throw(); do("THROW_F",f,b)
            self.cd=COOLDOWN["throw"]; return "Throw"
        if r<cuts[4]:
            do("D1",f,b); self.cd=COOLDOWN["d1"]; return "D1"
        if r<cuts[5]:
            do("D3",f,b); self.cd=COOLDOWN["d3"]; return "D3 [low]"
        if r<cuts[6]:
            combo_b1214_upknee(f,b); self.cd=COOLDOWN["b1214_upknee"]; return "B1214~DB3 [+4]"
        if r<cuts[7]:
            self.mixup.used_tackle(); combo_212_tackle(f,b)
            self.cd=COOLDOWN["212_tackle"]; return "212~BF3"
        if r<cuts[8]:
            self.mixup.used_slide(); combo_12_slide(f,b)
            self.cd=COOLDOWN["12_slide"]; return "12~BF4 [fast low]"
        if r<cuts[9]:
            combo_f43_upknee(f,b); self.cd=COOLDOWN["f43_upknee"]; return "F43~DB3 [+4]"
        if r<cuts[10]:
            do("D4",f,b); self.cd=COOLDOWN["d4"]; return "D4 [low]"
        if r<cuts[11]:
            do("B2",f,b); self.cd=COOLDOWN["b2"]; return "B2 [armor break]"
        if r<cuts[12]:
            combo_212_ghostball(f,b); self.cd=COOLDOWN["212_ghost"]; return "212~BF1"
        if r<cuts[13]:
            self.mixup.used_slide(); combo_b214_slide(f,b)
            self.cd=COOLDOWN["b214_slide"]; return "B214~BF4"
        if r<cuts[14] and dist<self.THROW_DIST:
            self.mixup.used_throw(); do("THROW_B",f,b)
            self.cd=COOLDOWN["throw"]; return "Back Throw"
        combo_b1214_ghostball(f,b); self.cd=COOLDOWN["b1214_ghost"]; return "B1214~BF1 [pushback]"

    # ── Punish ──
    def _punish(self,dist,p2):
        f,b=self.fwd,self.bwd
        if p2['hp']<0.15 and dist<self.PB_DIST:
            combo_f3_launch(f,b); self.cd=COOLDOWN["f3_launch"]; return "PUNISH: F3→212→BF1"
        if dist<self.PB_DIST:
            r=np.random.random()
            if r<0.30: combo_212_tackle(f,b); self.cd=COOLDOWN["212_tackle"]; return "PUNISH: 212~BF3"
            if r<0.55: combo_21_upknee(f,b); self.cd=COOLDOWN["21_upknee"]; return "PUNISH: 21~DB3 [+4]"
            if r<0.75: do("D1",f,b); self.cd=COOLDOWN["d1"]; return "PUNISH: D1"
            combo_b1214_tackle(f,b); self.cd=COOLDOWN["b1214_tackle"]; return "PUNISH: B1214~BF3"
        if dist<self.MID_DIST:
            r=np.random.random()
            if r<0.40: do("B3",f,b); self.cd=COOLDOWN["b3"]; return "PUNISH: B3"
            if r<0.70: do("F4",f,b); self.cd=COOLDOWN["f4"]; return "PUNISH: F4"
            combo_raw_tackle(f,b); self.cd=COOLDOWN["raw_tackle"]; return "PUNISH: BF3"
        combo_raw_slide_amp(f,b); self.cd=COOLDOWN["raw_slide_amp"]; return "PUNISH: BF4A [far]"

    def reset(self):
        self.cd=0; self.blocking=False; self.block_low=False
        self.block_timer=0; self.fatal_used=False
        self.threat.reset(); self.mixup.reset()


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
if __name__=="__main__":
    print("="*70)
    print("  NOOB SAIBOT BOT — The Shadow Wraith")
    print("="*70)
    print()
    print("  Shadow Slide (low) vs Shadow Tackle (mid) — 50/50 from strings")
    print("  Ghost Ball zoning | Upknee +4 pressure | Teleport crossups")
    print("  B1,2,1,4 main string into cancel mixups")
    print()

    vision=VisionEngine(); vision.start()
    print(">> Waiting for match lock...")
    while not vision.ready: time.sleep(0.1)
    print(">> Locked.\n")

    bot=NoobSaibotBot(); tick=time.time()

    try:
        while True:
            elapsed=time.time()-tick
            if elapsed<FRAME: time.sleep(FRAME-elapsed)
            tick=time.time()
            state=vision.get_state()
            if not state: continue
            p1,p2=state["p1"],state["p2"]
            action=bot.decide(p1,p2)
            if action in ("GUARDING","GUARDING [not safe]","HOLDING BLOCK"): continue
            dist=abs(p1['x']-p2['x'])
            print(
                f"Dist:{dist:>5.0f} | "
                f"NOB:{p1['hp']*1000:>4.0f} | "
                f"OPP:{p2['hp']*1000:>4.0f} | "
                f"Dmg:{bot.threat.frames_since_our_dmg:>3} | "
                f"Apr:{bot.threat.opp_approach_frames:>2} | "
                f"BT:{bot.block_timer:>3} | "
                f"CD:{bot.cd:>2} | "
                f"S:{bot.mixup.slide_count} T:{bot.mixup.tackle_count} "
                f"Th:{bot.mixup.throw_count} | "
                f"{action}"
            )
            if p1['hp']<=0.01 or p2['hp']<=0.01:
                print("\n>> Round over.\n")
                gamepad.reset(); gamepad.update()
                bot.reset(); time.sleep(2.5)
    except KeyboardInterrupt:
        print("\n>> Bot offline.")
    finally:
        gamepad.reset(); gamepad.update()
        vision.running=False; vision.join()