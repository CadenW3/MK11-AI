import gymnasium as gym
from gymnasium import spaces
import numpy as np

SUBZERO_MOVES = {
    0: {"name": "Idle", "frames": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    1: {"name": "Walk Forward", "frames": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, 
    2: {"name": "Walk Back", "frames": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    3: {"name": "Stand Block", "frames": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    4: {"name": "Crouch", "frames": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, 
    5: {"name": "Crouch Block", "frames": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    
    # Attacks: [Startup, Active, Recovery, Damage, Hitbox_W, Hitbox_H, Hitbox_Y, Type, Hit_Stun, Blk_Stun, Push, Launch]
    6: {"name": "1 (High Jab)", "frames": [7, 2, 13, 30, 50, 20, 90, 0, 15, -2, 10, 0]}, 
    7: {"name": "D1 (Mid Poke)", "frames": [7, 2, 11, 20, 55, 20, 40, 1, 11, -5, 5, 0]}, 
    8: {"name": "B3 (Low Kick)", "frames": [13, 3, 18, 40, 65, 20, 10, 2, 18, -7, 15, 0]}, 
    9: {"name": "F2 (Overhead)", "frames": [19, 3, 21, 60, 55, 40, 80, 3, 25, -12, 20, 0]}, 
    10: {"name": "Slide (Launch)", "frames": [11, 9, 28, 80, 90, 30, 0, 2, 0, -20, 30, 25]}, 
    11: {"name": "Forward Throw", "frames": [10, 2, 20, 130, 35, 30, 80, 4, 0, 0, 50, 0]}, 
    
    12: {"name": "Roll Forward", "frames": [0, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, 
    13: {"name": "Roll Back", "frames": [0, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    14: {"name": "Delay Wakeup", "frames": [0, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
}

class MK11AdvancedEnv(gym.Env):
    def __init__(self):
        super(MK11AdvancedEnv, self).__init__()
        self.action_space = spaces.Discrete(len(SUBZERO_MOVES))
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
            high=np.array([1920, 1920, 1080, 1080, 1000, 1000, 200, 200], dtype=np.float32),
            dtype=np.float32
        )

        self.max_health = 1000
        self.walk_speed = 8 
        self.base_gravity = 1.5 
        self.stand_hurtbox = (40, 120)
        self.crouch_hurtbox = (50, 70)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.sz = self.create_fighter(200) # Start in from the left edge
        
        random_distance = np.random.randint(40, 401)
        self.k = self.create_fighter(self.sz["x"] + random_distance)
        
        self.frames_elapsed = 0
        return self._get_obs(), {}

    def create_fighter(self, start_x):
        return {
            "x": float(start_x), "y": 0.0, "vy": 0.0,
            "health": float(self.max_health), "meter": 0.0,
            "state": 0, "timer": 0, "current_move": 0,
            "blocking": 0, "crouching": 0,
            "combo_count": 0, "tech_timer": 0, "invincible": 0
        }

    def _get_obs(self):
        return np.array([
            self.sz["x"], self.k["x"], 
            self.sz["y"], self.k["y"],
            self.sz["health"], self.k["health"], 
            self.sz["meter"], self.k["meter"]
        ], dtype=np.float32)

    def check_aabb_collision(self, ax, ay, aw, ah, dx, dy, dw, dh):
        return (ax < dx + dw and ax + aw > dx and ay < dy + dh and ay + ah > dy)

    def apply_gravity_and_juggling(self, fighter):
        if fighter["y"] > 0 or fighter["vy"] > 0:
            fighter["y"] += fighter["vy"]
            current_gravity = self.base_gravity + (fighter["combo_count"] * 0.25)
            fighter["vy"] -= current_gravity
            
            if fighter["y"] <= 0: 
                fighter["y"] = 0.0
                fighter["vy"] = 0.0
                if fighter["state"] == 4: 
                    fighter["state"] = 6 
                    fighter["timer"] = 40 
                    fighter["invincible"] = 1
                    fighter["combo_count"] = 0 

    def process_combat(self, attacker, defender, move_data, reward):
        hw, hh = self.crouch_hurtbox if defender["crouching"] else self.stand_hurtbox
        aw, ah = move_data[4], move_data[5]
        ax = attacker["x"] + 20 
        ay = attacker["y"] + move_data[6]
        hit_type = move_data[7]
        
        if hit_type == 0 and defender["crouching"]:
            return reward, False 
            
        if not self.check_aabb_collision(ax, ay, aw, ah, defender["x"], defender["y"], hw, hh):
            return reward, False 
            
        if hit_type == 4: 
            if defender["y"] > 0 or defender["crouching"]: 
                return reward, False 
            if defender["tech_timer"] > 0:
                attacker["x"] -= 40
                defender["x"] += 40
                return reward, True 
            else:
                defender["health"] -= move_data[3]
                defender["state"] = 6 
                defender["timer"] = 60
                defender["invincible"] = 1
                return reward + 50.0, True

        is_blocked = False
        if defender["blocking"] == 1 and hit_type != 2: 
            is_blocked = True
        elif defender["blocking"] == 2 and hit_type != 3: 
            is_blocked = True

        if is_blocked:
            defender["health"] -= move_data[3] * 0.15 
            defender["state"] = 5 
            defender["timer"] = abs(move_data[9])
            defender["x"] += move_data[10] 
        else:
            if defender["invincible"]: return reward, False 
            
            defender["combo_count"] += 1
            scaling_factor = 0.9 ** (defender["combo_count"] - 1)
            actual_damage = move_data[3] * scaling_factor
            
            defender["health"] -= actual_damage
            reward += (actual_damage * 2.0) 
            
            defender["state"] = 4 
            defender["timer"] = move_data[8]
            defender["x"] += move_data[10]
            
            if move_data[11] > 0: 
                defender["vy"] = move_data[11]

        return reward, True

    def step(self, action):
        # --- THE TIME PENALTY FIX (-0.1 keeps it aggressive but winnable) ---
        reward = -0.1 
        
        terminated = False
        truncated = False
        self.frames_elapsed += 1

        self.apply_gravity_and_juggling(self.sz)
        self.apply_gravity_and_juggling(self.k)

        self.sz["crouching"] = 0
        self.sz["blocking"] = 0

        if self.sz["state"] == 0: 
            if action == 1: self.sz["x"] = min(self.sz["x"] + self.walk_speed, self.k["x"] - 30) 
            elif action == 2: self.sz["x"] = max(self.sz["x"] - self.walk_speed, 0) 
            elif action == 3: self.sz["blocking"] = 1 
            elif action == 4: self.sz["crouching"] = 1 
            elif action == 5: 
                self.sz["crouching"] = 1
                self.sz["blocking"] = 2 
            
            elif action >= 6 and action <= 11: 
                self.sz["current_move"] = action
                self.sz["state"] = 1 
                self.sz["timer"] = SUBZERO_MOVES[action]["frames"][0]

        elif self.sz["state"] == 6: 
            if action == 12: 
                self.sz["state"] = 3 
                self.sz["timer"] = 30 
                self.sz["x"] += 80
            elif action == 13: 
                self.sz["state"] = 3 
                self.sz["timer"] = 30 
                self.sz["x"] -= 80
            elif action == 14: 
                self.sz["timer"] += 30 

        if self.sz["state"] == 1: 
            self.sz["timer"] -= 1
            if self.sz["timer"] <= 0:
                self.sz["state"] = 2 
                self.sz["timer"] = SUBZERO_MOVES[self.sz["current_move"]]["frames"][1]

        elif self.sz["state"] == 2: 
            move_data = SUBZERO_MOVES[self.sz["current_move"]]["frames"]
            reward, hit_registered = self.process_combat(self.sz, self.k, move_data, reward)
            
            if hit_registered:
                self.sz["state"] = 3 
                self.sz["timer"] = move_data[2]
            else:
                self.sz["timer"] -= 1
                if self.sz["timer"] <= 0:
                    self.sz["state"] = 3 
                    self.sz["timer"] = move_data[2]
                    # No Whiff Penalty = No Fear

        elif self.sz["state"] in [3, 4, 5]: 
            self.sz["timer"] -= 1
            if self.sz["timer"] <= 0:
                self.sz["state"] = 0
                self.sz["combo_count"] = 0 

        elif self.sz["state"] == 6: 
            self.sz["timer"] -= 1
            if self.sz["timer"] <= 0:
                self.sz["state"] = 0
                self.sz["invincible"] = 0

        if self.k["state"] in [3, 4, 5, 6]:
            self.k["timer"] -= 1
            if self.k["timer"] <= 0:
                self.k["state"] = 0
                self.k["invincible"] = 0
                if self.k["state"] != 4: self.k["combo_count"] = 0
        if self.k["tech_timer"] > 0: self.k["tech_timer"] -= 1

        # --- STAGE BOUNDARIES (Prevents OutOfBounds Crash) ---
        self.k["x"] = max(0.0, min(self.k["x"], 1900.0)) 
        self.sz["x"] = max(0.0, min(self.sz["x"], 1900.0)) 

        if self.k["health"] <= 0:
            reward += 1000.0
            terminated = True
        elif self.sz["health"] <= 0:
            reward -= 1000.0
            terminated = True

        if self.frames_elapsed > 3600: 
            truncated = True

        return self._get_obs(), reward, terminated, truncated, {}