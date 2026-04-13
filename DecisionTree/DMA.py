"""
DMA.py — MK11 Memory Reader

Reads game state via Direct Memory Access at 200Hz.
Inputs are decoded as string lists: ["DWN", "FP", "BLCK", ...]

Button map (from MK11 PlayerInfo.h enum):
  Bit 0    (1)     = UP
  Bit 1    (2)     = DWN  (Down)
  Bit 2    (4)     = LFT  (Left)
  Bit 3    (8)     = RGT  (Right)
  Bit 4    (16)    = BP   (Triangle/Y — button 2)
  Bit 5    (32)    = FK   (Cross/A — button 3)
  Bit 6    (64)    = FP   (Square/X — button 1)
  Bit 7    (128)   = BK   (Circle/B — button 4)
  Bit 8    (256)   = UNK
  Bit 9    (512)   = RST  (Reset)
  Bit 11   (2048)  = AST  (Assist)
  Bit 12   (4096)  = THRW (Throw)
  Bit 13   (8192)  = INT  (Interact / Amplify)
  Bit 14   (16384) = FLIP (Flip Stance)
  Bit 15   (32768) = BLCK (Block)

Player data dict:
  hp       — float 0.0-1.0
  x        — float world X position
  y        — float world Y position (>0 = airborne)
  inputs   — list[str] decoded button names
  raw_inp  — int raw bitmask
"""

import pymem
import pymem.process
import pymem.pattern
import struct
import threading
import time
import ctypes

ctypes.windll.user32.SetProcessDPIAware()


# ═══════════════════════════════════════════════════════════════════════
# BUTTON BITMASK DECODE TABLE
# ═══════════════════════════════════════════════════════════════════════
_BUTTON_MAP = [
    (1,     "UP"),
    (2,     "DWN"),
    (4,     "LFT"),
    (8,     "RGT"),
    (16,    "BP"),     # Triangle/Y — button 2
    (32,    "FK"),     # Cross/A   — button 3
    (64,    "FP"),     # Square/X  — button 1
    (128,   "BK"),     # Circle/B  — button 4
    (256,   "UNK"),
    (512,   "RST"),
    (2048,  "AST"),
    (4096,  "THRW"),
    (8192,  "INT"),    # Interact / Amplify
    (16384, "FLIP"),
    (32768, "BLCK"),
]

FACE_BUTTONS     = frozenset({"FP", "BP", "FK", "BK"})
DIRECTION_BUTTONS = frozenset({"UP", "DWN", "LFT", "RGT"})


def decode_buttons(mask):
    """Decode raw bitmask into list of button name strings."""
    if mask == 0:
        return []
    return [name for bit, name in _BUTTON_MAP if mask & bit]


# ── Helper functions for input analysis (used by bots) ──

def has_attack(inputs):
    """True if any face button is pressed."""
    for b in inputs:
        if b in FACE_BUTTONS:
            return True
    return False


def has_low_attack(inputs):
    """True if DWN + any face button = low attack."""
    return "DWN" in inputs and has_attack(inputs)


def has_jump_attack(inputs):
    """True if UP + any face button = jump-in attack."""
    return "UP" in inputs and has_attack(inputs)


def has_overhead(inputs):
    """True if face button without DWN (standing/forward = mid/high)."""
    return has_attack(inputs) and "DWN" not in inputs


def has_throw(inputs):
    return "THRW" in inputs


def has_block(inputs):
    return "BLCK" in inputs


def is_jumping(inputs):
    return "UP" in inputs


def is_crouching(inputs):
    return "DWN" in inputs and not has_attack(inputs)


def get_face_button(inputs):
    """Return the first face button pressed, or None."""
    for b in inputs:
        if b in FACE_BUTTONS:
            return b
    return None


def inputs_to_str(inputs):
    """Join input list to compact string for logging."""
    return "+".join(inputs) if inputs else "NONE"


# ═══════════════════════════════════════════════════════════════════════
# SPECIAL MOVE DETECTION (sequence-based)
# ═══════════════════════════════════════════════════════════════════════

def detect_special_motion(input_history, current_inputs):
    """Check if recent directional inputs + current face button = special move.

    Looks at the last 15 frames of input history for QCF (D,F), QCB (D,B),
    or other motion patterns followed by a face button press.

    Args:
        input_history: deque of input lists (last 15 frames)
        current_inputs: current frame's input list

    Returns:
        str or None: "QCF_FP", "QCB_FK", "DP_BP", etc. or None
    """
    if not has_attack(current_inputs):
        return None

    face = get_face_button(current_inputs)
    if not face:
        return None

    # Flatten recent directional inputs from history
    recent_dirs = []
    for frame_inputs in input_history:
        for btn in frame_inputs:
            if btn in DIRECTION_BUTTONS:
                recent_dirs.append(btn)

    if len(recent_dirs) < 2:
        return None

    # Look for motion patterns in the recent directional stream
    dir_str = " ".join(recent_dirs[-8:])  # last 8 directional inputs

    # Quarter circle forward: DWN → RGT (or DWN → LFT depending on facing)
    if "DWN" in recent_dirs[-6:]:
        if "RGT" in recent_dirs[-4:] or "LFT" in recent_dirs[-4:]:
            return f"QC_{face}"

    # Down-back motion (common for defensive specials)
    if "DWN" in recent_dirs[-6:] and ("LFT" in recent_dirs[-4:] or "RGT" in recent_dirs[-4:]):
        return f"DB_{face}"

    # Back-forward motion (tackle/charge type)
    dirs_last6 = recent_dirs[-6:]
    if (("LFT" in dirs_last6 and "RGT" in dirs_last6) or
            ("RGT" in dirs_last6 and "LFT" in dirs_last6)):
        return f"BF_{face}"

    return None


# ═══════════════════════════════════════════════════════════════════════
# MEMORY READER
# ═══════════════════════════════════════════════════════════════════════

class VisionEngine(threading.Thread):
    """Reads MK11 game state at 200Hz via DMA.

    Public interface:
      .ready       — bool, True when both players are locked
      .get_state() — returns {"p1": {...}, "p2": {...}} or None

    Player dict keys:
      hp       — float 0.0 to 1.0
      x        — float world X
      y        — float world Y (>0 = airborne)
      inputs   — list[str] decoded button names
      raw_inp  — int raw bitmask
    """

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.ready = False
        self._lock = threading.Lock()

        self.p1_char_ptr = 0
        self.p2_char_ptr = 0
        self.p1_info_ptr = 0
        self.p2_info_ptr = 0
        self._data = None
        self.game_info_base = None

        try:
            self.pm = pymem.Pymem("mk11.exe")
            self.module = pymem.process.module_from_name(
                self.pm.process_handle, "mk11.exe"
            )
            self._resolve_base()
        except Exception as e:
            print(f"[!] DMA init failed: {e}")
            self.running = False

    def _resolve_base(self):
        sig = b"\x40\x53\x48\x83\xEC\x20\x0F\xB6\xDA\x45\x33\xC0\x8B\xD1\x48\x8B\x0D"
        addr = pymem.pattern.pattern_scan_module(
            self.pm.process_handle, self.module, sig
        )
        if not addr:
            print("[!] FATAL: GameInfo signature not found")
            self.running = False
            return
        ip = addr + 17
        offset = struct.unpack('<i', self.pm.read_bytes(ip, 4))[0]
        self.game_info_base = ip + offset + 4
        print(f">> GameInfo base: {hex(self.game_info_base)}")

    def _find_char_ptr(self, info_ptr):
        if not info_ptr:
            return 0
        try:
            info_bytes = self.pm.read_bytes(info_ptr, 0x1000)
        except Exception:
            return 0
        for i in range(0, len(info_bytes) - 8, 8):
            test_ptr = struct.unpack('<Q', info_bytes[i:i+8])[0]
            try:
                if 0x10000000000 < test_ptr < 0x6FFFFFFFFFF:
                    if (self.pm.read_longlong(test_ptr + 0x250) > 0
                            and self.pm.read_longlong(test_ptr + 0x10E0) > 0):
                        hp = self.pm.read_float(test_ptr + 0xC20)
                        if 0.0 <= hp <= 1.1:
                            return test_ptr
            except Exception:
                continue
        return 0

    def _refresh_ptrs(self):
        try:
            game_info_ptr = self.pm.read_longlong(self.game_info_base)
            self.p1_info_ptr = self.pm.read_longlong(game_info_ptr + 0x778)
            self.p2_info_ptr = self.pm.read_longlong(game_info_ptr + 0x780)
            self.p1_char_ptr = self._find_char_ptr(self.p1_info_ptr)
            self.p2_char_ptr = self._find_char_ptr(self.p2_info_ptr)
            if self.p1_char_ptr and self.p2_char_ptr:
                print(f">> [LOCKED] P1: {hex(self.p1_char_ptr)} | P2: {hex(self.p2_char_ptr)}")
        except Exception:
            self.p1_char_ptr = 0
            self.p2_char_ptr = 0

    def _read_player(self, char_ptr, info_ptr):
        try:
            hp = self.pm.read_float(char_ptr + 0xC20)
            transform_ptr = self.pm.read_longlong(char_ptr + 0x20)
            x = self.pm.read_float(transform_ptr + 0x11C)
            y = self.pm.read_float(transform_ptr + 0x120)
            gamepad_ptr = self.pm.read_longlong(info_ptr + 0x30)
            raw_mask = self.pm.read_uint(gamepad_ptr + 0x1C) if gamepad_ptr else 0
            return {
                "hp": hp,
                "x": x,
                "y": y,
                "inputs": decode_buttons(raw_mask),
                "raw_inp": raw_mask,
            }
        except Exception:
            return None

    def run(self):
        while self.running:
            if not self.p1_char_ptr or not self.p2_char_ptr:
                self._refresh_ptrs()
                time.sleep(0.005)
                continue

            p1 = self._read_player(self.p1_char_ptr, self.p1_info_ptr)
            p2 = self._read_player(self.p2_char_ptr, self.p2_info_ptr)

            if p1 and p2:
                with self._lock:
                    self._data = {"p1": p1, "p2": p2}
                    self.ready = True
            else:
                self.p1_char_ptr = 0
                self.p2_char_ptr = 0
                self.ready = False

            time.sleep(0.005)

    def get_state(self):
        with self._lock:
            return self._data