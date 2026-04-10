import time
import struct
import numpy as np
import vgamepad as vg
import threading
import ctypes
import pymem
import pymem.process
import pymem.pattern
import gymnasium as gym
from gymnasium import spaces

from sb3_contrib import RecurrentPPO

ctypes.windll.user32.SetProcessDPIAware()

print(">> Booting MK11 Sim2Real DMA Pipeline...")
gamepad = vg.VX360Gamepad()

# =========================================================
# FRAME DATA & COOLDOWN DICTIONARY (Imported from Simulator)
# =========================================================
SUBZERO_MOVES = {
    10: {"name": "Forward Throw",  "startup": 10, "rec": 35},
    11: {"name": "Back Throw",     "startup": 10, "rec": 35},
    12: {"name": "Hop Attack",     "startup": 11, "rec": 22},
    13: {"name": "Wakeup U3",      "startup": 11, "rec": 30},
    14: {"name": "FATAL BLOW",     "startup": 20, "rec": 60},
    15: {"name": "D1 Poke",        "startup": 6,  "rec": 15},
    16: {"name": "D2 Uppercut",    "startup": 9,  "rec": 35},
    17: {"name": "D3 Low Poke",    "startup": 9,  "rec": 18},
    18: {"name": "D4 Sweep",       "startup": 11, "rec": 22},
    19: {"name": "Stand 1",        "startup": 7,  "rec": 16},
    20: {"name": "Stand 2",        "startup": 9,  "rec": 20},
    21: {"name": "Stand 3",        "startup": 11, "rec": 22},
    22: {"name": "Stand 4",        "startup": 12, "rec": 24},
    23: {"name": "B1",             "startup": 13, "rec": 20},
    24: {"name": "F2 Overhead",    "startup": 19, "rec": 35},
    25: {"name": "B3",             "startup": 13, "rec": 22},
    26: {"name": "F4",             "startup": 16, "rec": 28},
    27: {"name": "Jump Punch",     "startup": 8,  "rec": 20},
    28: {"name": "Jump Kick",      "startup": 10, "rec": 30},
    # Specials
    48: {"name": "Ice Ball",       "startup": 18, "rec": 60},
    49: {"name": "Slide",          "startup": 11, "rec": 55}, 
    50: {"name": "Creeping Ice",   "startup": 16, "rec": 40},
}

# =========================================================
# THE DMA VISION ENGINE
# =========================================================
class VisionEngine(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.lock = threading.Lock()
        self.running = True
        self.ready = False
        
        self.p1_char_ptr = 0
        self.p2_char_ptr = 0
        self.p1_info_ptr = 0
        self.p2_info_ptr = 0
        
        self.data = {
            "p1": {"hp": 1.0, "x": 0.0, "y": 0.0, "state": 0},
            "p2": {"hp": 1.0, "x": 0.0, "y": 0.0, "state": 0}
        }

        try:
            self.pm = pymem.Pymem("mk11.exe")
            self.client_module = pymem.process.module_from_name(self.pm.process_handle, "mk11.exe")
            game_info_sig = b"\x40\x53\x48\x83\xEC\x20\x0F\xB6\xDA\x45\x33\xC0\x8B\xD1\x48\x8B\x0D"
            sig_address = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.client_module, game_info_sig)
            
            if sig_address:
                instruction_ptr = sig_address + 17
                offset = struct.unpack('<i', self.pm.read_bytes(instruction_ptr, 4))[0]
                self.game_info_base = instruction_ptr + offset + 4
            else:
                self.running = False
        except Exception as e:
            self.running = False

    def _verify_fighter(self, ptr):
        try:
            if not (0x10000000000 < ptr < 0x6FFFFFFFFFF): return False
            if not (0x10000000000 < self.pm.read_longlong(ptr + 0x20) < 0x6FFFFFFFFFF): return False
            if not (0x10000000000 < self.pm.read_longlong(ptr + 0x250) < 0x6FFFFFFFFFF): return False
            hp = self.pm.read_float(ptr + 0xC20)
            if not (0.0 <= hp <= 1.1): return False
            return True
        except: return False

    def _get_character_data(self, char_ptr, info_ptr):
        try:
            hp = self.pm.read_float(char_ptr + 0xC20)
            transform_ptr = self.pm.read_longlong(char_ptr + 0x20)
            x = self.pm.read_float(transform_ptr + 0x11C) 
            y = self.pm.read_float(transform_ptr + 0x120) 

            vm_ptr = self.pm.read_longlong(char_ptr + 0x10E0)
            state_id = self.pm.read_uint(vm_ptr + 0x228) if vm_ptr else 0
            
            return {"hp": hp, "x": x, "y": y, "state": state_id}
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
                            if self._verify_fighter(test_ptr): return test_ptr
                        return 0

                    self.p1_char_ptr = find_char(self.p1_info_ptr)
                    self.p2_char_ptr = find_char(self.p2_info_ptr)
                    continue

                p1_data = self._get_character_data(self.p1_char_ptr, self.p1_info_ptr)
                p2_data = self._get_character_data(self.p2_char_ptr, self.p2_info_ptr)

                if not p1_data or not p2_data: raise ValueError()

                with self.lock:
                    self.data["p1"] = p1_data
                    self.data["p2"] = p2_data
                    self.ready = True
                
            except Exception:
                self.p1_char_ptr = 0
                self.p2_char_ptr = 0
                self.ready = False
            
            time.sleep(0.005) 

    def get_dma_state(self):
        with self.lock:
            return self.data["p1"], self.data["p2"]

vision = VisionEngine()
vision.start()
while not vision.ready: time.sleep(0.1)

# =========================================================
# HARDWARE EXECUTION
# =========================================================
def execute_multibinary_intent(action):
    gamepad.reset()
    if action[0]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
    if action[1]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
    if action[2]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
    if action[3]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
    if action[4]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X) 
    if action[5]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y) 
    if action[6]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A) 
    if action[7]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B) 
    if action[8]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)  
    if action[9]: gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER) 
    if action[10]: gamepad.left_trigger_float(1.0)  
    if action[11]: gamepad.right_trigger_float(1.0) 
    gamepad.update()

# =========================================================
# THE LIVE GYM ENVIRONMENT
# =========================================================
class LiveMK11Env(gym.Env):
    def __init__(self):
        super().__init__()
        self.action_space = spaces.MultiBinary(12) 
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(60,), dtype=np.float32)
        
        self.max_stage_width = 2500.0
        self.max_jump_height = 500.0
        self.history = np.zeros((10, 6), dtype=np.float32)
        self.last_step_time = time.time()
        
        # THE FIX: Cooldown tracker for the live bot!
        self.p1_cooldown_frames = 0

    def reset(self, seed=None, options=None):
        self.history = np.zeros((10, 6), dtype=np.float32)
        self.p1_cooldown_frames = 0
        gamepad.reset()
        gamepad.update()
        obs, p1, p2 = self._get_obs()
        return obs, {}

    def _get_obs(self):
        p1, p2 = vision.get_dma_state()
        
        raw_dist = abs(p1['x'] - p2['x'])
        norm_dist = np.clip(raw_dist / self.max_stage_width, 0.0, 1.0)
        norm_p1_y = np.clip(p1['y'] / self.max_jump_height, 0.0, 1.0)
        norm_p2_y = np.clip(p2['y'] / self.max_jump_height, 0.0, 1.0)
        
        facing = 1.0 if p2['x'] > p1['x'] else -1.0
        
        current_frame = np.array([p1['hp'], p2['hp'], norm_dist, norm_p1_y, norm_p2_y, facing], dtype=np.float32)
        
        self.history = np.roll(self.history, shift=-1, axis=0)
        self.history[-1, :] = current_frame
        
        return self.history.flatten(), p1, p2

    def _decode_to_macro(self, action, p1_x, p2_x):
        """Translates the 12 buttons into the 0-63 macro ID so we can look up frame data"""
        up, dn, lf, rt = action[0], action[1], action[2], action[3]
        sq, tr, cr, ci = action[4], action[5], action[6], action[7]
        
        p_right = p1_x < p2_x
        fwd = rt if p_right else lf
        bwd = lf if p_right else rt

        if dn and fwd and sq: return 48 # Ice Ball
        if dn and fwd and cr: return 49 # Slide
        if up and (sq or tr): return 27 # Jump Punch
        if up and (cr or ci): return 28 # Jump Kick
        if dn and sq: return 15 # D1
        if dn and tr: return 16 # D2
        if dn and cr: return 17 # D3
        if dn and ci: return 18 # D4
        if sq: return 19 # S1
        if tr: return 20 # S2
        if cr: return 21 # S3
        if ci: return 22 # S4
        if bwd and sq: return 23 # B1
        if fwd and tr: return 24 # F2
        if bwd and cr: return 25 # B3
        if fwd and ci: return 26 # F4
        
        return 0 # Not an attack

    def step(self, action):
        # 1. STRICT 60 FPS THROTTLE (Fixes the Time Warp)
        target_frame_time = 1.0 / 60.0
        elapsed_time = time.time() - self.last_step_time
        if elapsed_time < target_frame_time:
            time.sleep(target_frame_time - elapsed_time)
        self.last_step_time = time.time()

        # 2. THE COOLDOWN LOCKOUT (Fixes the Spamming)
        obs, p1, p2 = self._get_obs()
        macro_id = self._decode_to_macro(action, p1['x'], p2['x'])

        if self.p1_cooldown_frames > 0:
            # If animating, ignore AI intent completely and release buttons
            action = np.zeros(12, dtype=np.int32)
            self.p1_cooldown_frames -= 1
            action_name = "ANIMATING..."
        else:
            # If AI throws an attack, apply the cooldown lock!
            if macro_id in SUBZERO_MOVES:
                frames = SUBZERO_MOVES[macro_id]["startup"] + SUBZERO_MOVES[macro_id]["rec"]
                self.p1_cooldown_frames = int(frames)
                action_name = SUBZERO_MOVES[macro_id]["name"]
            else:
                action_name = "MOVING/BLOCKING"

        # 3. Press the filtered buttons (Held for exactly 1/60th of a second naturally by the loop)
        execute_multibinary_intent(action)
        
        # 4. Console Logging (Added coordinates so you can verify it sees distance!)
        terminated = p1['hp'] <= 0.01 or p2['hp'] <= 0.01
        
        dist = abs(p1['x'] - p2['x'])
        print(f"Dist: {dist:04.0f} | SZ: {p1['hp']*1000:4.0f} HP | KOL: {p2['hp']*1000:4.0f} HP | Action: {action_name}")
        
        return obs, 0.0, terminated, False, {}

# =========================================================
# START THE LIVE DEPLOYMENT PIPELINE
# =========================================================
if __name__ == '__main__':
    live_env = LiveMK11Env()
    print("\n==============================================")
    print("READY FOR LIVE GAMEPLAY")
    print("==============================================")
    
    try:
        model = RecurrentPPO.load("models/sim_model_sz.zip", env=live_env, device="cuda")
        obs, _ = live_env.reset()
        
        lstm_states = None
        episode_starts = np.ones((1,), dtype=bool)

        while True:
            action, lstm_states = model.predict(obs, state=lstm_states, episode_start=episode_starts, deterministic=False)
            obs, rewards, dones, info, _ = live_env.step(action)
            episode_starts = np.array([dones], dtype=bool)
            
            if dones:
                gamepad.reset(); gamepad.update()
                time.sleep(2) 
                obs, _ = live_env.reset()
                
    except FileNotFoundError:
        print("[!] Model missing.")
    except KeyboardInterrupt:
        pass
    finally:
        gamepad.reset(); gamepad.update()
        vision.running = False; vision.join()