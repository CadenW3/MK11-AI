import numpy as np
import os
import time
import argparse
import torch
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3.common.vec_env import VecEnv
from sb3_contrib import RecurrentPPO

# ==========================================
# SUB-ZERO FULL FRAME DATA (P1 - 64 Actions)
# ==========================================
SUBZERO_MOVES = {
    # System & Movement (0-9)
    0:  {"name": "Idle",           "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    1:  {"name": "Walk Forward",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    2:  {"name": "Walk Back",      "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    3:  {"name": "Stand Block",    "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    4:  {"name": "Crouch",         "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    5:  {"name": "Crouch Block",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    6:  {"name": "Dash Forward",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 15},
    7:  {"name": "Dash Back",      "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 15},
    8:  {"name": "Forward Roll",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 4,  "rec": 30},
    9:  {"name": "Backward Roll",  "reach": 0,    "dmg": 0,   "type": "none",       "startup": 4,  "rec": 30},

    # Throws & System Attacks (10-14)
    10: {"name": "Forward Throw",  "reach": 40,   "dmg": 130, "type": "unblockable","startup": 10, "rec": 35},
    11: {"name": "Back Throw",     "reach": 40,   "dmg": 130, "type": "unblockable","startup": 10, "rec": 35},
    12: {"name": "Hop Attack",     "reach": 60,   "dmg": 30,  "type": "overhead",   "startup": 11, "rec": 22},
    13: {"name": "Wakeup U3",      "reach": 65,   "dmg": 50,  "type": "mid",        "startup": 11, "rec": 30},
    14: {"name": "FATAL BLOW",     "reach": 400,  "dmg": 320, "type": "mid",        "startup": 20, "rec": 60},

    # Pokes & Uppercuts (15-18)
    15: {"name": "D1 Poke",        "reach": 55,   "dmg": 20,  "type": "mid",        "startup": 6,  "rec": 15},
    16: {"name": "D2 Uppercut",    "reach": 80,   "dmg": 140, "type": "high",       "startup": 9,  "rec": 35},
    17: {"name": "D3 Low Poke",    "reach": 60,   "dmg": 20,  "type": "low",        "startup": 9,  "rec": 18},
    18: {"name": "D4 Sweep",       "reach": 85,   "dmg": 30,  "type": "low",        "startup": 11, "rec": 22},

    # Base Standing Normals (19-26)
    19: {"name": "Stand 1",        "reach": 55,   "dmg": 20,  "type": "high",       "startup": 7,  "rec": 16},
    20: {"name": "Stand 2",        "reach": 60,   "dmg": 30,  "type": "high",       "startup": 9,  "rec": 20},
    21: {"name": "Stand 3",        "reach": 65,   "dmg": 40,  "type": "high",       "startup": 11, "rec": 22},
    22: {"name": "Stand 4",        "reach": 70,   "dmg": 50,  "type": "high",       "startup": 12, "rec": 24},
    23: {"name": "B1",             "reach": 65,   "dmg": 30,  "type": "mid",        "startup": 13, "rec": 20},
    24: {"name": "F2 Overhead",    "reach": 110,  "dmg": 70,  "type": "overhead",   "startup": 19, "rec": 35},
    25: {"name": "B3",             "reach": 75,   "dmg": 30,  "type": "low",        "startup": 13, "rec": 22},
    26: {"name": "F4",             "reach": 85,   "dmg": 50,  "type": "mid",        "startup": 16, "rec": 28},

    # Jump Attacks (27-28)
    27: {"name": "Jump Punch (J1/J2)","reach": 75, "dmg": 50, "type": "overhead",   "startup": 8,  "rec": 20},
    28: {"name": "Jump Kick (J3/J4)", "reach": 110,"dmg": 70, "type": "overhead",   "startup": 10, "rec": 30},

    # Strings - 1 Series (29-32)
    29: {"name": "1,1",            "reach": 60,   "dmg": 50,  "type": "high",       "startup": 10, "rec": 18},
    30: {"name": "1,1,1",          "reach": 60,   "dmg": 90,  "type": "high",       "startup": 12, "rec": 20},
    31: {"name": "1,2",            "reach": 65,   "dmg": 60,  "type": "mid",        "startup": 11, "rec": 22},
    32: {"name": "1,2,4",          "reach": 75,   "dmg": 110, "type": "mid",        "startup": 14, "rec": 25},

    # Strings - 2 Series (33-36)
    33: {"name": "2,1",            "reach": 65,   "dmg": 50,  "type": "mid",        "startup": 10, "rec": 20},
    34: {"name": "2,1,2",          "reach": 70,   "dmg": 90,  "type": "mid",        "startup": 14, "rec": 24},
    35: {"name": "2,3",            "reach": 75,   "dmg": 70,  "type": "mid",        "startup": 13, "rec": 22},
    36: {"name": "2,3,4",          "reach": 80,   "dmg": 110, "type": "mid",        "startup": 16, "rec": 26},

    # Strings - Back/Forward Series (37-47)
    37: {"name": "B1,4",           "reach": 70,   "dmg": 60,  "type": "low",        "startup": 14, "rec": 25},
    38: {"name": "B1,4,3",         "reach": 85,   "dmg": 116, "type": "mid",        "startup": 20, "rec": 45}, 
    39: {"name": "F2,4",           "reach": 115,  "dmg": 100, "type": "mid",        "startup": 18, "rec": 30},
    40: {"name": "B3,2",           "reach": 80,   "dmg": 90,  "type": "mid",        "startup": 15, "rec": 25},
    41: {"name": "B3,2,1",         "reach": 85,   "dmg": 120, "type": "mid",        "startup": 16, "rec": 30},
    42: {"name": "F4,2",           "reach": 90,   "dmg": 80,  "type": "mid",        "startup": 15, "rec": 22},
    43: {"name": "F4,2,3",         "reach": 95,   "dmg": 110, "type": "mid",        "startup": 17, "rec": 26},
    44: {"name": "Chinese Ninja",  "reach": 65,   "dmg": 30,  "type": "mid",        "startup": 13, "rec": 20}, 
    45: {"name": "Cold Encounter", "reach": 60,   "dmg": 30,  "type": "high",       "startup": 9,  "rec": 20},
    46: {"name": "Unchained (B3)",     "reach": 75, "dmg": 30, "type": "low",       "startup": 13, "rec": 22},
    47: {"name": "Frosty (F4)",        "reach": 85, "dmg": 50, "type": "mid",       "startup": 16, "rec": 28},

    # Specials (48-55)
    48: {"name": "Ice Ball",       "reach": 1900, "dmg": 50,  "type": "projectile", "startup": 18, "rec": 60},
    49: {"name": "Slide",          "reach": 300,  "dmg": 80,  "type": "low",        "startup": 11, "rec": 55}, 
    50: {"name": "Creeping Ice",   "reach": 140,  "dmg": 70,  "type": "low",        "startup": 16, "rec": 40},
    51: {"name": "Amp Ice Ball",   "reach": 1900, "dmg": 80,  "type": "projectile", "startup": 18, "rec": 45},
    52: {"name": "Amp Slide",      "reach": 300,  "dmg": 120, "type": "low",        "startup": 11, "rec": 65},
    53: {"name": "Amp Creeping Ice","reach": 140, "dmg": 120, "type": "low",        "startup": 16, "rec": 45},
    
    # Empty buffers
    54: {"name": "Interact FWD",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 15, "rec": 20},
    55: {"name": "Interact BWD",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 15, "rec": 20},
    56: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    57: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    58: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    59: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    60: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    61: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    62: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    63: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
}

# ==========================================
# KOLLECTOR FULL FRAME DATA (P2 - 64 Actions)
# ==========================================
KOLLECTOR_MOVES = {
    # System & Movement (0-9)
    0:  {"name": "Idle",           "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    1:  {"name": "Walk Forward",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    2:  {"name": "Walk Back",      "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    3:  {"name": "Stand Block",    "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    4:  {"name": "Crouch",         "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    5:  {"name": "Crouch Block",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 0},
    6:  {"name": "Dash Forward",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 15},
    7:  {"name": "Dash Back",      "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 15},
    8:  {"name": "Forward Roll",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 4,  "rec": 30},
    9:  {"name": "Backward Roll",  "reach": 0,    "dmg": 0,   "type": "none",       "startup": 4,  "rec": 30},

    # Throws & System Attacks (10-14)
    10: {"name": "Forward Throw",  "reach": 45,   "dmg": 130, "type": "unblockable","startup": 10, "rec": 35},
    11: {"name": "Back Throw",     "reach": 45,   "dmg": 130, "type": "unblockable","startup": 10, "rec": 35},
    12: {"name": "Hop Attack",     "reach": 65,   "dmg": 30,  "type": "overhead",   "startup": 12, "rec": 22},
    13: {"name": "Wakeup U3",      "reach": 70,   "dmg": 50,  "type": "mid",        "startup": 12, "rec": 30}, 
    14: {"name": "FATAL BLOW",     "reach": 400,  "dmg": 320, "type": "mid",        "startup": 18, "rec": 60},

    # Pokes & Uppercuts (15-18)
    15: {"name": "D1 Poke",        "reach": 60,   "dmg": 20,  "type": "mid",        "startup": 7,  "rec": 16},
    16: {"name": "D2 Uppercut",    "reach": 85,   "dmg": 140, "type": "high",       "startup": 10, "rec": 35},
    17: {"name": "D3 Low Poke",    "reach": 65,   "dmg": 20,  "type": "low",        "startup": 10, "rec": 18},
    18: {"name": "D4 Sweep",       "reach": 100,  "dmg": 30,  "type": "low",        "startup": 14, "rec": 24},

    # Base Standing Normals (19-26)
    19: {"name": "Stand 1",        "reach": 60,   "dmg": 20,  "type": "high",       "startup": 8,  "rec": 18},
    20: {"name": "Stand 2",        "reach": 65,   "dmg": 30,  "type": "high",       "startup": 10, "rec": 22},
    21: {"name": "Stand 3",        "reach": 70,   "dmg": 40,  "type": "high",       "startup": 12, "rec": 24},
    22: {"name": "Stand 4",        "reach": 75,   "dmg": 50,  "type": "high",       "startup": 11, "rec": 24},
    23: {"name": "F1",             "reach": 70,   "dmg": 30,  "type": "mid",        "startup": 11, "rec": 20},
    24: {"name": "F2",             "reach": 80,   "dmg": 30,  "type": "mid",        "startup": 13, "rec": 22},
    25: {"name": "B1",             "reach": 75,   "dmg": 30,  "type": "mid",        "startup": 15, "rec": 24},
    26: {"name": "F4 Mid Kick",    "reach": 140,  "dmg": 60,  "type": "mid",        "startup": 11, "rec": 30}, 

    # Jump Attacks (27-28)
    27: {"name": "Jump Punch (J1)","reach": 80, "dmg": 50, "type": "overhead",   "startup": 9,  "rec": 22},
    28: {"name": "Jump Kick (J3)", "reach": 115,"dmg": 70, "type": "overhead",   "startup": 11, "rec": 32},

    # Strings - 1 & 2 Series (29-34)
    29: {"name": "1,3",            "reach": 70,   "dmg": 70,  "type": "high",       "startup": 12, "rec": 22},
    30: {"name": "1,3,1",          "reach": 75,   "dmg": 100, "type": "mid",        "startup": 16, "rec": 25},
    31: {"name": "F1,2",           "reach": 75,   "dmg": 59,  "type": "mid",        "startup": 14, "rec": 20},
    32: {"name": "F1,2,D1",        "reach": 80,   "dmg": 109, "type": "low",        "startup": 18, "rec": 25},
    33: {"name": "F1,2,D2",        "reach": 80,   "dmg": 109, "type": "overhead",   "startup": 20, "rec": 30},
    34: {"name": "F2,2",           "reach": 85,   "dmg": 60,  "type": "mid",        "startup": 15, "rec": 20},

    # Strings - Command Grabs & B/F Series (35-43)
    35: {"name": "F2,2,1+3",       "reach": 90,   "dmg": 119, "type": "mid",        "startup": 20, "rec": 45},
    36: {"name": "B1,2",           "reach": 80,   "dmg": 80,  "type": "mid",        "startup": 15, "rec": 20},
    37: {"name": "B1,2,2",         "reach": 85,   "dmg": 130, "type": "mid",        "startup": 18, "rec": 28},
    38: {"name": "2,1+3",          "reach": 65,   "dmg": 60,  "type": "mid",        "startup": 14, "rec": 24},
    39: {"name": "2,1+3,4",        "reach": 70,   "dmg": 110, "type": "unblockable","startup": 16, "rec": 40},
    40: {"name": "B2,3",           "reach": 110,  "dmg": 110, "type": "overhead",   "startup": 16, "rec": 40},
    41: {"name": "F3,1",           "reach": 90,   "dmg": 60,  "type": "mid",        "startup": 14, "rec": 22},
    42: {"name": "F3,1,2",         "reach": 95,   "dmg": 90,  "type": "high",       "startup": 16, "rec": 24},
    43: {"name": "F3,1,2,3",       "reach": 100,  "dmg": 140, "type": "mid",        "startup": 20, "rec": 30},

    # Staggers & Utilities (44-47)
    44: {"name": "4,4",            "reach": 85,   "dmg": 60,  "type": "mid",        "startup": 15, "rec": 25},
    45: {"name": "4,4,3",          "reach": 90,   "dmg": 110, "type": "low",        "startup": 18, "rec": 35},
    46: {"name": "B3",             "reach": 95,   "dmg": 40,  "type": "mid",        "startup": 14, "rec": 22},
    47: {"name": "B4",             "reach": 100,  "dmg": 50,  "type": "low",        "startup": 15, "rec": 25},

    # Specials (48-55)
    48: {"name": "Bolas",          "reach": 1900, "dmg": 60,  "type": "projectile", "startup": 17, "rec": 50},
    49: {"name": "Demonic Mace",   "reach": 160,  "dmg": 90,  "type": "overhead",   "startup": 25, "rec": 45}, 
    50: {"name": "Relic Lure",     "reach": 180,  "dmg": 70,  "type": "mid",        "startup": 15, "rec": 35},
    51: {"name": "Amp Bolas",      "reach": 1900, "dmg": 90,  "type": "projectile", "startup": 17, "rec": 45},
    52: {"name": "Amp Mace",       "reach": 160,  "dmg": 130, "type": "overhead",   "startup": 25, "rec": 40},
    53: {"name": "Amp Relic Lure", "reach": 180,  "dmg": 110, "type": "mid",        "startup": 15, "rec": 30},
    
    # Empty buffers
    54: {"name": "Interact FWD",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 15, "rec": 20},
    55: {"name": "Interact BWD",   "reach": 0,    "dmg": 0,   "type": "none",       "startup": 15, "rec": 20},
    56: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    57: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    58: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    59: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    60: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    61: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    62: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
    63: {"name": "Wait Frame",     "reach": 0,    "dmg": 0,   "type": "none",       "startup": 0,  "rec": 1},
}

NUM_ACTIONS = 64
_type_map = {"none": 0, "high": 1, "mid": 2, "low": 3, "overhead": 4, "unblockable": 5, "projectile": 6}

# Pre-compute Tables
_sz_reach   = np.array([SUBZERO_MOVES[i]["reach"]   for i in range(NUM_ACTIONS)], dtype=np.float32)
_sz_dmg     = np.array([SUBZERO_MOVES[i]["dmg"]     for i in range(NUM_ACTIONS)], dtype=np.float32)
_sz_startup = np.array([SUBZERO_MOVES[i]["startup"] for i in range(NUM_ACTIONS)], dtype=np.float32)
_sz_rec     = np.array([SUBZERO_MOVES[i]["rec"]     for i in range(NUM_ACTIONS)], dtype=np.float32)
_sz_type    = np.array([_type_map[SUBZERO_MOVES[i]["type"]] for i in range(NUM_ACTIONS)], dtype=np.int32)

_kol_reach   = np.array([KOLLECTOR_MOVES[i]["reach"]   for i in range(NUM_ACTIONS)], dtype=np.float32)
_kol_dmg     = np.array([KOLLECTOR_MOVES[i]["dmg"]     for i in range(NUM_ACTIONS)], dtype=np.float32)
_kol_startup = np.array([KOLLECTOR_MOVES[i]["startup"] for i in range(NUM_ACTIONS)], dtype=np.float32)
_kol_rec     = np.array([KOLLECTOR_MOVES[i]["rec"]     for i in range(NUM_ACTIONS)], dtype=np.float32)
_kol_type    = np.array([_type_map[KOLLECTOR_MOVES[i]["type"]] for i in range(NUM_ACTIONS)], dtype=np.int32)

class MK11VecEnv(VecEnv):
    def __init__(self, num_envs: int, training_side: str = "sz"):
        self.training_side = training_side
        self.n = num_envs
        
        self.MAX_STAGE_X = 2500.0
        self.MAX_JUMP_Y = 500.0
        self.WALK_SPEED = 15.0
        self.GRAVITY = 20.0
        self.delay_frames = 4
        self.max_frames = 3600 

        observation_space = spaces.Box(low=-1.0, high=1.0, shape=(60,), dtype=np.float32)
        
        # THE FIX: Switch to a single integer choice (0 to 63)
        action_space = spaces.Discrete(NUM_ACTIONS) 
        super().__init__(num_envs, observation_space, action_space)

        self.p1_pos = np.zeros((num_envs, 2), dtype=np.float32)
        self.p2_pos = np.zeros((num_envs, 2), dtype=np.float32)
        self.p1_hp  = np.zeros(num_envs, dtype=np.float32)
        self.p2_hp  = np.zeros(num_envs, dtype=np.float32)
        
        self.p1_y_vel = np.zeros(num_envs, dtype=np.float32)
        self.p2_y_vel = np.zeros(num_envs, dtype=np.float32)
        
        self.p1_cd = np.zeros(num_envs, dtype=np.int32)
        self.p2_cd = np.zeros(num_envs, dtype=np.int32)
        self.p1_stun = np.zeros(num_envs, dtype=np.int32)
        self.p2_stun = np.zeros(num_envs, dtype=np.int32)
        self.hitstop_timer = np.zeros(num_envs, dtype=np.int32)

        self.history = np.zeros((num_envs, 10, 6), dtype=np.float32)
        self.ep_returns = np.zeros(num_envs, dtype=np.float32)
        self.ep_lengths = np.zeros(num_envs, dtype=np.int32)
        
        # The buffers now hold single integers!
        self.action_buffer = np.zeros((num_envs, self.delay_frames), dtype=np.int32)
        self.opp_action_buffer = np.zeros((num_envs, self.delay_frames), dtype=np.int32)
        self.opp_actions = np.zeros(num_envs, dtype=np.int32)

    def reset(self):
        return self._reset_all(np.arange(self.n))

    def _reset_all(self, idx):
        self.p1_pos[idx, 0] = 600.0; self.p1_pos[idx, 1] = 0.0
        self.p2_pos[idx, 0] = 1200.0; self.p2_pos[idx, 1] = 0.0
        self.p1_hp[idx] = 1.0; self.p2_hp[idx] = 1.0
        self.p1_y_vel[idx] = 0.0; self.p2_y_vel[idx] = 0.0
        self.p1_cd[idx] = 0; self.p2_cd[idx] = 0
        self.p1_stun[idx] = 0; self.p2_stun[idx] = 0
        self.hitstop_timer[idx] = 0

        self.action_buffer[idx] = 0
        self.opp_action_buffer[idx] = 0
        self.ep_returns[idx] = 0.0
        self.ep_lengths[idx] = 0
        self.history[idx] = 0.0
        
        return self._get_obs()

    def _get_obs(self) -> np.ndarray:
        raw_dist = np.abs(self.p1_pos[:, 0] - self.p2_pos[:, 0])
        norm_dist = np.clip(raw_dist / self.MAX_STAGE_X, 0.0, 1.0)
        norm_p1_y = np.clip(self.p1_pos[:, 1] / self.MAX_JUMP_Y, 0.0, 1.0)
        norm_p2_y = np.clip(self.p2_pos[:, 1] / self.MAX_JUMP_Y, 0.0, 1.0)
        facing = np.where(self.p2_pos[:, 0] > self.p1_pos[:, 0], 1.0, -1.0)

        if self.training_side == "sz":
            current_frame = np.column_stack([self.p1_hp, self.p2_hp, norm_dist, norm_p1_y, norm_p2_y, facing])
        else:
            current_frame = np.column_stack([self.p2_hp, self.p1_hp, norm_dist, norm_p2_y, norm_p1_y, -facing])

        self.history = np.roll(self.history, shift=-1, axis=1)
        self.history[:, -1, :] = current_frame
        return self.history.reshape(self.n, -1).astype(np.float32)

    def get_opponent_obs(self) -> np.ndarray:
        opp_history = np.copy(self.history)
        temp_hp = np.copy(opp_history[:, :, 0])
        opp_history[:, :, 0] = opp_history[:, :, 1]
        opp_history[:, :, 1] = temp_hp
        temp_y = np.copy(opp_history[:, :, 3])
        opp_history[:, :, 3] = opp_history[:, :, 4]
        opp_history[:, :, 4] = temp_y
        opp_history[:, :, 5] = -opp_history[:, :, 5]
        return opp_history.reshape(self.n, -1).astype(np.float32)

    def set_opponent_actions(self, actions: np.ndarray):
        self.opp_actions = actions

    def step_async(self, actions):
        self.action_buffer = np.roll(self.action_buffer, shift=-1, axis=1)
        self.action_buffer[:, -1] = actions

        self.opp_action_buffer = np.roll(self.opp_action_buffer, shift=-1, axis=1)
        self.opp_action_buffer[:, -1] = self.opp_actions

    def step_wait(self):
        self.ep_lengths += 1
        
        # Actions are already decoded integers! No complex function needed!
        p1_macros = self.action_buffer[:, 0]
        p2_macros = self.opp_action_buffer[:, 0]

        prev_p1_hp, prev_p2_hp = np.copy(self.p1_hp), np.copy(self.p2_hp)
        dist = np.abs(self.p1_pos[:, 0] - self.p2_pos[:, 0])

        in_hitstop = self.hitstop_timer > 0

        p1_blocking_high = (p1_macros == 3) | (p1_macros == 2)
        p1_blocking_low = (p1_macros == 5)
        p2_blocking_high = (p2_macros == 3) | (p2_macros == 2)
        p2_blocking_low = (p2_macros == 5)

        p1_locked = (self.p1_cd > 0) | (self.p1_stun > 0)
        p2_locked = (self.p2_cd > 0) | (self.p2_stun > 0)

        p1_macros = np.where(p1_locked, 0, p1_macros)
        p2_macros = np.where(p2_locked, 0, p2_macros)

        p1_blocking_high = np.where(p1_locked, False, p1_blocking_high)
        p1_blocking_low = np.where(p1_locked, False, p1_blocking_low)
        p2_blocking_high = np.where(p2_locked, False, p2_blocking_high)
        p2_blocking_low = np.where(p2_locked, False, p2_blocking_low)

        p1_is_attacking = (p1_macros != 0) & (_sz_dmg[p1_macros] > 0)
        p2_is_attacking = (p2_macros != 0) & (_kol_dmg[p2_macros] > 0)

        self.p1_cd = np.where(~in_hitstop, np.where(p1_is_attacking, (_sz_startup[p1_macros] + _sz_rec[p1_macros]).astype(np.int32), np.maximum(0, self.p1_cd - 1)), self.p1_cd)
        self.p2_cd = np.where(~in_hitstop, np.where(p2_is_attacking, (_kol_startup[p2_macros] + _kol_rec[p2_macros]).astype(np.int32), np.maximum(0, self.p2_cd - 1)), self.p2_cd)
        
        self.p1_stun = np.where(~in_hitstop, np.maximum(0, self.p1_stun - 1), self.p1_stun)
        self.p2_stun = np.where(~in_hitstop, np.maximum(0, self.p2_stun - 1), self.p2_stun)

        p1_jumping = np.isin(p1_macros, [27, 28]) & (self.p1_pos[:, 1] <= 0) & ~p1_locked
        self.p1_y_vel = np.where(~in_hitstop, np.where(p1_jumping, 45.0, self.p1_y_vel - self.GRAVITY), self.p1_y_vel)
        self.p1_pos[:, 1] = np.where(~in_hitstop, np.maximum(0, self.p1_pos[:, 1] + self.p1_y_vel), self.p1_pos[:, 1])

        facing = np.where(self.p2_pos[:, 0] > self.p1_pos[:, 0], 1.0, -1.0)
        self.p1_pos[:, 0] += np.where(~in_hitstop & (p1_macros == 1), self.WALK_SPEED * facing, 0.0) 
        self.p1_pos[:, 0] -= np.where(~in_hitstop & (p1_macros == 2), self.WALK_SPEED * facing, 0.0) 
        
        self.p1_pos[:, 0] = np.clip(self.p1_pos[:, 0], 0.0, self.MAX_STAGE_X)
        self.p2_pos[:, 0] = np.clip(self.p2_pos[:, 0], 0.0, self.MAX_STAGE_X)

        p1_atk_type = _sz_type[p1_macros]
        p2_atk_type = _kol_type[p2_macros]

        p1_y_whiff = ((p1_atk_type == 2) | (p1_atk_type == 3)) & (self.p2_pos[:, 1] > 50.0)
        p2_y_whiff = ((p2_atk_type == 2) | (p2_atk_type == 3)) & (self.p1_pos[:, 1] > 50.0)

        p2_blocks_p1 = ((((p1_atk_type == 1) | (p1_atk_type == 4)) & p2_blocking_high) | ((p1_atk_type == 3) & p2_blocking_low) | ((p1_atk_type == 2) & (p2_blocking_high | p2_blocking_low)) | ((p1_atk_type == 6) & (p2_blocking_high | p2_blocking_low)))
        p1_blocks_p2 = ((((p2_atk_type == 1) | (p2_atk_type == 4)) & p1_blocking_high) | ((p2_atk_type == 3) & p1_blocking_low) | ((p2_atk_type == 2) & (p1_blocking_high | p1_blocking_low)) | ((p2_atk_type == 6) & (p1_blocking_high | p1_blocking_low)))

        p1_clean_hit = p1_is_attacking & (dist <= _sz_reach[p1_macros]) & ~p1_y_whiff & ~p2_blocks_p1 & ~in_hitstop
        p2_clean_hit = p2_is_attacking & (dist <= _kol_reach[p2_macros]) & ~p2_y_whiff & ~p1_blocks_p2 & ~in_hitstop
        
        p1_blocked_hit = p1_is_attacking & (dist <= _sz_reach[p1_macros]) & ~p1_y_whiff & p2_blocks_p1 & ~in_hitstop
        p2_blocked_hit = p2_is_attacking & (dist <= _kol_reach[p2_macros]) & ~p2_y_whiff & p1_blocks_p2 & ~in_hitstop

        p1_dmg_dealt = np.where(p1_clean_hit, _sz_dmg[p1_macros], np.where(p1_blocked_hit, _sz_dmg[p1_macros] * 0.2, 0.0))
        p2_dmg_dealt = np.where(p2_clean_hit, _kol_dmg[p2_macros], np.where(p2_blocked_hit, _kol_dmg[p2_macros] * 0.2, 0.0))

        self.p2_hp = np.maximum(0, self.p2_hp - (p1_dmg_dealt / 1000.0))
        self.p1_hp = np.maximum(0, self.p1_hp - (p2_dmg_dealt / 1000.0))

        self.p2_stun = np.where(p1_clean_hit, 25, self.p2_stun)
        self.p1_stun = np.where(p2_clean_hit, 25, self.p1_stun)

        new_hit = p1_clean_hit | p2_clean_hit | p1_blocked_hit | p2_blocked_hit
        self.hitstop_timer = np.where(new_hit, 5, np.maximum(0, self.hitstop_timer - 1))

        damage_done = (prev_p2_hp - self.p2_hp) * 1000.0
        damage_taken = (prev_p1_hp - self.p1_hp) * 1000.0
        
        reward = (damage_done * 5.0) - (damage_taken * 1.5)
        reward += np.where(dist <= 250.0, 0.5, 0.0) 
        reward -= np.where(dist >= 600.0, 0.5, 0.0)

        # NOTE: Mashing penalty has been entirely REMOVED since Discrete space cannot mash!

        time_over = self.ep_lengths >= self.max_frames
        p1_wins_timeout = time_over & (self.p1_hp > self.p2_hp)
        p2_wins_timeout = time_over & (self.p2_hp > self.p1_hp)

        died = (self.p1_hp <= 0) | (self.p2_hp <= 0)
        terminated = died | time_over

        reward += np.where(self.p2_hp <= 0, 1000.0, 0.0)
        reward -= np.where(self.p1_hp <= 0, 1000.0, 0.0)
        reward += np.where(p2_wins_timeout, 1000.0, 0.0)
        reward -= np.where(p1_wins_timeout, 1000.0, 0.0)
        is_draw = time_over & (self.p1_hp == self.p2_hp)
        reward -= np.where(is_draw, 1000.0, 0.0)

        self.ep_returns += reward

        terminal_obs = self._get_obs()
        infos = [{} for _ in range(self.n)]
        for i in range(self.n):
            if terminated[i]:
                infos[i]["terminal_observation"] = terminal_obs[i]
                infos[i]["episode"] = {"r": self.ep_returns[i], "l": self.ep_lengths[i]}

        if np.any(terminated):
            self._reset_all(np.where(terminated)[0])

        return self._get_obs(), reward, terminated, infos

    def close(self): pass
    def env_is_wrapped(self, wrapper_class, indices=None): return [False] * self.n
    def env_method(self, method_name, *args, indices=None, **kwargs): raise NotImplementedError("Use batched methods directly")
    def get_attr(self, attr_name, indices=None): return [getattr(self, attr_name)] * self.n
    def set_attr(self, attr_name, value, indices=None): setattr(self, attr_name, value)
    def seed(self, seed=None): pass

# ==========================================
# TRAINING LOOP (RECURRENT LSTM)
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", type=str, default="sz")
    args = parser.parse_args()

    print(f">> Initializing MK11 Simulation ({args.side})...")
    
    if not os.path.exists("models"): os.makedirs("models")

    env = MK11VecEnv(num_envs=32, training_side=args.side)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_path = f"models/sim_model_{args.side}.zip"

    policy_kwargs = dict(lstm_hidden_size=256, n_lstm_layers=1)

    if os.path.exists(model_path):
        print(f">> Resuming training from {model_path}...")
        model = RecurrentPPO.load(model_path, env=env, device=device)
    else:
        print(">> Generating NEW Recurrent Brain...")
        model = RecurrentPPO("MlpLstmPolicy", env, verbose=1, device=device, 
                             policy_kwargs=policy_kwargs, n_steps=512, batch_size=128)

    try:
        model.learn(total_timesteps=100_000_000, log_interval=10)
    except KeyboardInterrupt:
        print("\n>> Training interrupted. Saving progress...")
    finally:
        model.save(model_path)
        print(f">> Brain saved to {model_path}")