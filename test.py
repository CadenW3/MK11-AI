import pymem
import pymem.process
import pymem.pattern
import struct
import threading
import time
import ctypes

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
            
            print(">> Scanning for GameInfo...")
            game_info_sig = b"\x40\x53\x48\x83\xEC\x20\x0F\xB6\xDA\x45\x33\xC0\x8B\xD1\x48\x8B\x0D"
            gi_sig_address = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.client_module, game_info_sig)
            
            if gi_sig_address:
                instruction_ptr = gi_sig_address + 17
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
        buttons = []
        if mask & 1:     buttons.append("UP")
        if mask & 2:     buttons.append("DWN")
        if mask & 4:     buttons.append("LFT")
        if mask & 8:     buttons.append("RGT")
        if mask & 16:    buttons.append("BP")   
        if mask & 32:    buttons.append("FK")   
        if mask & 64:    buttons.append("FP")   
        if mask & 128:   buttons.append("BK")   
        if mask & 512:   buttons.append("RST")  
        if mask & 4096:  buttons.append("THRW") 
        if mask & 8192:  buttons.append("INT")  
        if mask & 32768: buttons.append("BLCK") 
        return buttons

    def _get_character_data(self, char_ptr, info_ptr):
        try:
            hp = self.pm.read_float(char_ptr + 0xC20)
            transform_ptr = self.pm.read_longlong(char_ptr + 0x20)
            x = self.pm.read_float(transform_ptr + 0x11C) 
            y = self.pm.read_float(transform_ptr + 0x120) 

            gamepad_ptr = self.pm.read_longlong(info_ptr + 0x30)
            button_mask = self.pm.read_uint(gamepad_ptr + 0x1C) if gamepad_ptr else 0

            # Get Character Name
            char_name = "UNKNOWN"
            try:
                char_info_ptr = self.pm.read_longlong(info_ptr + 0xD8)
                if char_info_ptr:
                    char_name = self.pm.read_bytes(char_info_ptr, 32).split(b'\x00')[0].decode('utf-8', errors='ignore')
            except: pass

            # Extract exact 32-bit Hash
            action_hash = "IDLE"
            try:
                vm_proc_ptr = self.pm.read_longlong(char_ptr + 0x10E0)
                if vm_proc_ptr:
                    func_hash = self.pm.read_uint(vm_proc_ptr + 0x168)
                    action_hash = str(func_hash)
            except: pass

            return {
                "name": char_name, "hp": hp, "x": x, "y": y, 
                "inputs": self.decode_buttons(button_mask),
                "action": action_hash
            }
        except: return None

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
                    continue

                with self.lock:
                    self.data["p1"] = self._get_character_data(self.p1_char_ptr, self.p1_info_ptr)
                    self.data["p2"] = self._get_character_data(self.p2_char_ptr, self.p2_info_ptr)

                if not self.data["p1"] or not self.data["p2"]:
                    self.p1_char_ptr = 0; self.p2_char_ptr = 0

            except:
                self.p1_char_ptr = 0; self.p2_char_ptr = 0
            
            time.sleep(0.005)

if __name__ == "__main__":
    engine = VisionEngine()
    engine.start()
    
    last_p1_hash = ""
    last_p2_hash = ""

    print(">> Logger Online.")
    try:
        while True:
            with engine.lock:
                p1 = engine.data["p1"]
                p2 = engine.data["p2"]

            if p1 and p2:
                if p1['action'] != last_p1_hash or p2['action'] != last_p2_hash:
                    p1_in = "+".join(p1['inputs']) if p1['inputs'] else "NONE"
                    p2_in = "+".join(p2['inputs']) if p2['inputs'] else "NONE"
                    print(f"P1 ({p1['name']}) | Inp: {p1_in:<15} | Hash: {p1['action']}")
                    print(f"P2 ({p2['name']}) | Inp: {p2_in:<15} | Hash: {p2['action']}")
                    print("-" * 70)
                    last_p1_hash = p1['action']
                    last_p2_hash = p2['action']
            time.sleep(0.005) 
    except KeyboardInterrupt:
        engine.running = False
        engine.join()