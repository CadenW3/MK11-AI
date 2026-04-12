import pymem
import pymem.process
import pymem.pattern
import struct
import threading
import time
import ctypes
from collections import deque

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
        """Maps bitmask to button names from the True MK11 PlayerInfo.h Enum"""
        buttons = []
        if mask & 1:     buttons.append("UP")
        if mask & 2:     buttons.append("DWN")
        if mask & 4:     buttons.append("LFT")
        if mask & 8:     buttons.append("RGT")
        if mask & 16:    buttons.append("BP")   # Triangle/Y
        if mask & 32:    buttons.append("FK")   # Cross/A
        if mask & 64:    buttons.append("FP")   # Square/X
        if mask & 128:   buttons.append("BK")   # Circle/B
        if mask & 256:   buttons.append("UNK")  
        if mask & 512:   buttons.append("RST")  # Reset
        if mask & 2048:  buttons.append("AST")  # Assist
        if mask & 4096:  buttons.append("THRW") # Throw
        if mask & 8192:  buttons.append("INT")  # Interact
        if mask & 16384: buttons.append("FLIP") # Flip Stance
        if mask & 32768: buttons.append("BLCK") # Block
        
        return buttons

    def _get_character_data(self, char_ptr, info_ptr):
        try:
            hp = self.pm.read_float(char_ptr + 0xC20)
            transform_ptr = self.pm.read_longlong(char_ptr + 0x20)
            x = self.pm.read_float(transform_ptr + 0x11C) 
            y = self.pm.read_float(transform_ptr + 0x120) 
            
            # Unreal Engine 4 Skeletal Mesh Pointer Chain (For future 3D bone tracking)
            # mesh_ptr = self.pm.read_longlong(char_ptr + 0x280) 
            # bone_array_ptr = self.pm.read_longlong(mesh_ptr + 0x4B0) # Transform array

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
            
            time.sleep(0.005) # 200 Hz Polling Rate for frame-perfect input reading

# =========================================================
# HEURISTIC ACTION & SPECIAL DECODER
# =========================================================
def get_action_name(inputs, y_pos, input_history):
    """ Translates raw engine buttons into fighting game terminology, including specials """
    
    # Check for Projectiles / Special Moves (Sequence Detection)
    # Most specials are D,B+Face or D,F+Face. We look at the last 15 frames of inputs.
    recent_dirs = [btn for frame in input_history for btn in frame if btn in ["DWN", "LFT", "RGT", "UP"]]
    face_buttons = [btn for btn in inputs if btn in ["FP", "BP", "FK", "BK"]]
    
    if face_buttons and "DWN" in recent_dirs:
        if "LFT" in recent_dirs or "RGT" in recent_dirs:
            return f"*** SPECIAL MOVE / PROJECTILE ({face_buttons[0]}) ***"

    # Standard Actions
    if y_pos > 10.0:
        if "FP" in inputs or "BP" in inputs: return "Jump Punch"
        if "FK" in inputs or "BK" in inputs: return "Jump Kick"
        return "JUMPING"
    
    if "BLCK" in inputs:
        if "DWN" in inputs: return "Crouch Block"
        return "Stand Block"
        
    if "THRW" in inputs: return "Throw Attempt"
    if "INT" in inputs: return "Interact / Amplifying"

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
# MAIN SCROLLING LOGGER & COMBO TRACKER
# =========================================================
if __name__ == "__main__":
    engine = VisionEngine()
    engine.start()

    print(">> Scanning for match...")
    
    # Input History Buffers (Rolling 15-frame window for Special Move detection)
    p1_input_history = deque(maxlen=15)
    p2_input_history = deque(maxlen=15)
    
    last_p1_input_str = ""
    last_p2_input_str = ""

    # DMA True Combo Tracker Variables
    p1_combo_count = 0
    p1_last_hp = 1.0
    p1_hitstun_frames = 0
    
    p2_combo_count = 0
    p2_last_hp = 1.0
    p2_hitstun_frames = 0

    try:
        while True:
            with engine.lock:
                p1 = engine.data["p1"]
                p2 = engine.data["p2"]

            if p1 and p2:
                p1_input_history.append(p1['inputs'])
                p2_input_history.append(p2['inputs'])
                
                # --- DMA COMBO TRACKER LOGIC ---
                # P1 Combo State
                if p1['hp'] < p1_last_hp - 0.005: 
                    p2_combo_count += 1
                    p1_hitstun_frames = 60 # Set arbitrary hitstun decay timer
                elif p1_hitstun_frames > 0:
                    p1_hitstun_frames -= 1
                    if p1_hitstun_frames == 0:
                        p2_combo_count = 0 # Combo dropped/ended
                p1_last_hp = p1['hp']

                # P2 Combo State
                if p2['hp'] < p2_last_hp - 0.005: 
                    p1_combo_count += 1
                    p2_hitstun_frames = 60 
                elif p2_hitstun_frames > 0:
                    p2_hitstun_frames -= 1
                    if p2_hitstun_frames == 0:
                        p1_combo_count = 0
                p2_last_hp = p2['hp']
                # -------------------------------

                p1_str = "+".join(p1['inputs']) if p1['inputs'] else "NONE"
                p2_str = "+".join(p2['inputs']) if p2['inputs'] else "NONE"

                # ONLY print when a button changes or a combo increments
                if p1_str != last_p1_input_str or p2_str != last_p2_input_str:
                    
                    p1_action = get_action_name(p1['inputs'], p1['y'], p1_input_history)
                    p2_action = get_action_name(p2['inputs'], p2['y'], p2_input_history)
                    
                    p1_combo_tag = f"[P1 COMBO: {p1_combo_count}]" if p1_combo_count > 1 else ""
                    p2_combo_tag = f"[P2 COMBO: {p2_combo_count}]" if p2_combo_count > 1 else ""
                    
                    print(f"P1 | HP: {p1['hp']*1000:>4.0f} | Pos: ({p1['x']:>7.2f}, {p1['y']:>6.2f}) | Inp: {p1_str:<15} | {p1_action:<25} {p1_combo_tag}")
                    print(f"P2 | HP: {p2['hp']*1000:>4.0f} | Pos: ({p2['x']:>7.2f}, {p2['y']:>6.2f}) | Inp: {p2_str:<15} | {p2_action:<25} {p2_combo_tag}")
                    print("-" * 110)
                    
                    last_p1_input_str = p1_str
                    last_p2_input_str = p2_str
            
            time.sleep(0.005) # Throttle to 200 FPS
    except KeyboardInterrupt:
        engine.running = False
        engine.join()
        print("\n>> Logger Offline. Scroll up to review your frame data!")