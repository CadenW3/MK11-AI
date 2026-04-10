import pymem
import pymem.process
import pymem.pattern
import struct
import threading
import time
import ctypes

ctypes.windll.user32.SetProcessDPIAware()


class MK11Memory:
    def __init__(self):
        self.pm = pymem.Pymem("mk11.exe")
        self.module = pymem.process.module_from_name(self.pm.process_handle, "mk11.exe")
        self.p1_char_ptr = 0
        self.p2_char_ptr = 0
        self.p1_info_ptr = 0
        self.p2_info_ptr = 0
        self.game_info_base = None
        self._resolve_base()

    def _resolve_base(self):
        sig = b"\x40\x53\x48\x83\xEC\x20\x0F\xB6\xDA\x45\x33\xC0\x8B\xD1\x48\x8B\x0D"
        addr = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.module, sig)
        if not addr:
            raise RuntimeError("GameInfo signature not found")
        ip = addr + 17
        offset = struct.unpack('<i', self.pm.read_bytes(ip, 4))[0]
        self.game_info_base = ip + offset + 4
        print(f">> GameInfo base: {hex(self.game_info_base)}")

    def _verify_fighter(self, ptr):
        try:
            if not (0x10000000000 < ptr < 0x6FFFFFFFFFF): return False
            if not (0x10000000000 < self.pm.read_longlong(ptr + 0x20) < 0x6FFFFFFFFFF): return False
            if not (0x10000000000 < self.pm.read_longlong(ptr + 0x250) < 0x6FFFFFFFFFF): return False
            hp = self.pm.read_float(ptr + 0xC20)
            return 0.0 <= hp <= 1.1
        except:
            return False

    def _find_char_ptr(self, info_ptr):
        if not info_ptr: return 0
        info_bytes = self.pm.read_bytes(info_ptr, 0x1000)
        for i in range(0, len(info_bytes) - 8, 8):
            test_ptr = struct.unpack('<Q', info_bytes[i:i+8])[0]
            if self._verify_fighter(test_ptr):
                return test_ptr
        return 0

    def _refresh_ptrs(self):
        game_info_ptr = self.pm.read_longlong(self.game_info_base)
        self.p1_info_ptr = self.pm.read_longlong(game_info_ptr + 0x778)
        self.p2_info_ptr = self.pm.read_longlong(game_info_ptr + 0x780)
        self.p1_char_ptr = self._find_char_ptr(self.p1_info_ptr)
        self.p2_char_ptr = self._find_char_ptr(self.p2_info_ptr)
        if self.p1_char_ptr and self.p2_char_ptr:
            print(f">> Locked P1: {hex(self.p1_char_ptr)} | P2: {hex(self.p2_char_ptr)}")

    def _ensure_ptrs(self):
        if not self.p1_char_ptr or not self.p2_char_ptr:
            self._refresh_ptrs()
        return bool(self.p1_char_ptr and self.p2_char_ptr)

    def _get_transform_ptr(self, char_ptr):
        return self.pm.read_longlong(char_ptr + 0x20)

    def _safe_read_uint(self, addr):
        try: return self.pm.read_uint(addr)
        except: return 0

    def _safe_read_longlong(self, addr):
        try: return self.pm.read_longlong(addr)
        except: return 0

    def _read_char_data(self, char_ptr, info_ptr):
        hp = self.pm.read_float(char_ptr + 0xC20)
        t = self._get_transform_ptr(char_ptr)
        x = self.pm.read_float(t + 0x11C)
        y = self.pm.read_float(t + 0x120)

        # ── ACTION ID at char_ptr + 0x5D0 ──
        # IDLE=453, BLOCK=358, ATTACK=varies (1,30,132,199,339,...)
        action_id = self._safe_read_uint(char_ptr + 0x5D0)

        # ── Raw gamepad (unreliable but useful for low/throw detection) ──
        gamepad_ptr = self._safe_read_longlong(info_ptr + 0x30)
        inputs = self._safe_read_uint(gamepad_ptr + 0x1C) if gamepad_ptr else 0

        return {
            "hp": hp, "x": x, "y": y,
            "action_id": action_id,
            "inputs": inputs,
        }

    def get_state(self):
        if not self._ensure_ptrs(): return None
        try:
            p1 = self._read_char_data(self.p1_char_ptr, self.p1_info_ptr)
            p2 = self._read_char_data(self.p2_char_ptr, self.p2_info_ptr)
            return {"p1": p1, "p2": p2}
        except:
            self.p1_char_ptr = 0
            self.p2_char_ptr = 0
            return None


class VisionEngine(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.ready = False
        self._lock = threading.Lock()
        self._data = None
        self._mem = MK11Memory()

    def run(self):
        while self.running:
            state = self._mem.get_state()
            if state:
                with self._lock:
                    self._data = state
                    self.ready = True
            else:
                self.ready = False
            time.sleep(0.005)

    def get_state(self):
        with self._lock:
            return self._data