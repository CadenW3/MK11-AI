import pymem
import pymem.process
import pymem.pattern
import struct
import threading
import time
import ctypes

# Force Windows to use raw pixels for coordinate accuracy
ctypes.windll.user32.SetProcessDPIAware()

class VisionEngine(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.lock = threading.Lock()
        
        self.p1_char_ptr = 0
        self.p2_char_ptr = 0
        self.p1_info_ptr = 0
        self.p2_info_ptr = 0
        self.data = {"p1": None, "p2": None}

        try:
            self.pm = pymem.Pymem("mk11.exe")
            self.client_module = pymem.process.module_from_name(self.pm.process_handle, "mk11.exe")
            
            game_info_sig = b"\x40\x53\x48\x83\xEC\x20\x0F\xB6\xDA\x45\x33\xC0\x8B\xD1\x48\x8B\x0D"
            sig_address = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.client_module, game_info_sig)
            
            if sig_address:
                instruction_ptr = sig_address + 17
                offset = struct.unpack('<i', self.pm.read_bytes(instruction_ptr, 4))[0]
                self.game_info_base = instruction_ptr + offset + 4
                print(f">> SUCCESS: GameInfo Base resolved at {hex(self.game_info_base)}")
            else:
                print("[!] FATAL: Could not find GameInfo signature.")
                self.running = False
        except Exception as e:
            print(f"[!] Initialization Error: {e}")
            self.running = False

    def decode_buttons(self, mask):
        """Maps bitmask to button names from PlayerInfo.h"""
        buttons = []
        if mask & 64:    buttons.append("FP") # Square/X
        if mask & 16:    buttons.append("BP") # Triangle/Y
        if mask & 32:    buttons.append("FK") # Cross/A
        if mask & 128:   buttons.append("BK") # Circle/B
        if mask & 4096:  buttons.append("THRW")
        if mask & 8192:  buttons.append("INT") # Interact
        if mask & 32768: buttons.append("BLCK")
        if mask & 1:     buttons.append("UP")
        if mask & 2:     buttons.append("DWN")
        if mask & 4:     buttons.append("LFT")
        if mask & 8:     buttons.append("RGT")
        return "+".join(buttons) if buttons else "NONE"

    def _get_character_data(self, char_ptr, info_ptr):
        try:
            hp = self.pm.read_float(char_ptr + 0xC20)
            transform_ptr = self.pm.read_longlong(char_ptr + 0x20)
            x = self.pm.read_float(transform_ptr + 0x11C) 
            y = self.pm.read_float(transform_ptr + 0x120) 

            gamepad_ptr = self.pm.read_longlong(info_ptr + 0x30)
            button_mask = self.pm.read_uint(gamepad_ptr + 0x1C) if gamepad_ptr else 0
            
            return {
                "hp": hp, "x": x, "y": y, 
                "inputs": self.decode_buttons(button_mask),
            }
        except:
            return None

    def run(self):
        while self.running:
            try:
                game_info_ptr = self.pm.read_longlong(self.game_info_base)

                if self.p1_char_ptr == 0 or self.p2_char_ptr == 0:
                    self.p1_info_ptr = self.pm.read_longlong(game_info_ptr + 0x778)
                    self.p2_info_ptr = self.pm.read_longlong(game_info_ptr + 0x780)

                    def find_char(info_ptr):
                        if not info_ptr: return 0
                        info_bytes = self.pm.read_bytes(info_ptr, 0x1000)
                        for i in range(0, len(info_bytes) - 8, 8):
                            test_ptr = struct.unpack('<Q', info_bytes[i:i+8])[0]
                            try:
                                if 0x10000000000 < test_ptr < 0x6FFFFFFFFFF:
                                    if self.pm.read_longlong(test_ptr + 0x250) > 0 and self.pm.read_longlong(test_ptr + 0x10E0) > 0:
                                        return test_ptr
                            except: continue
                        return 0

                    self.p1_char_ptr = find_char(self.p1_info_ptr)
                    self.p2_char_ptr = find_char(self.p2_info_ptr)
                    
                    if self.p1_char_ptr and self.p2_char_ptr:
                        print(f">> [LOCKED] P1: {hex(self.p1_char_ptr)} | P2: {hex(self.p2_char_ptr)}")
                    continue

                p1_data = self._get_character_data(self.p1_char_ptr, self.p1_info_ptr)
                p2_data = self._get_character_data(self.p2_char_ptr, self.p2_info_ptr)

                with self.lock:
                    self.data["p1"] = p1_data
                    self.data["p2"] = p2_data

                if not p1_data or not p2_data:
                    self.p1_char_ptr = 0
                    self.p2_char_ptr = 0

            except Exception:
                self.p1_char_ptr = 0
                self.p2_char_ptr = 0
            
            time.sleep(0.01)

# =========================================================
# HEURISTIC ACTION DECODER
# =========================================================
def get_action_name(inputs, y_pos):
    """ Translates raw engine buttons into fighting game terminology """
    if y_pos > 10.0:
        if "FP" in inputs or "BP" in inputs: return "Jump Punch"
        if "FK" in inputs or "BK" in inputs: return "Jump Kick"
        return "JUMPING"
    
    if "BLCK" in inputs:
        if "DWN" in inputs: return "Crouch Block"
        return "Stand Block"
        
    if "THRW" in inputs: return "Throw Attempt"

    if "DWN" in inputs:
        if "FP" in inputs: return "D1 Poke"
        if "BP" in inputs: return "D2 Uppercut"
        if "FK" in inputs: return "D3 Low Poke"
        if "BK" in inputs: return "D4 Sweep"
        return "CROUCHING"
        
    if "FP" in inputs: return "High Punch (1)"
    if "BP" in inputs: return "Mid/Overh (2)"
    if "FK" in inputs: return "Mid Kick (3)"
    if "BK" in inputs: return "Low/Mid Kick (4)"

    if "LFT" in inputs or "RGT" in inputs: return "WALKING"
    if "UP" in inputs: return "JUMP STARTUP"

    return "IDLE"

# =========================================================
# MAIN SCROLLING LOGGER
# =========================================================
if __name__ == "__main__":
    engine = VisionEngine()
    engine.start()

    print(">> Scanning for match...")
    
    last_p1_input = ""
    last_p2_input = ""

    try:
        while True:
            with engine.lock:
                p1 = engine.data["p1"]
                p2 = engine.data["p2"]

            if p1 and p2:
                # ONLY print when someone presses or releases a button
                if p1['inputs'] != last_p1_input or p2['inputs'] != last_p2_input:
                    
                    p1_action = get_action_name(p1['inputs'], p1['y'])
                    p2_action = get_action_name(p2['inputs'], p2['y'])
                    
                    print(f"P1 | HP: {p1['hp']*1000:>4.0f} | Pos: ({p1['x']:>7.2f}, {p1['y']:>6.2f}) | Input: {p1['inputs']:<12} | Action: {p1_action}")
                    print(f"P2 | HP: {p2['hp']*1000:>4.0f} | Pos: ({p2['x']:>7.2f}, {p2['y']:>6.2f}) | Input: {p2['inputs']:<12} | Action: {p2_action}")
                    print("-" * 90)
                    
                    last_p1_input = p1['inputs']
                    last_p2_input = p2['inputs']
            
            time.sleep(0.01)
    except KeyboardInterrupt:
        engine.running = False
        engine.join()
        print("\n>> Logger Offline. Scroll up to review your frame data!")