"""
Training script using the fully vectorized MK11VecEnv.
Hardware Profile: i7-14700K | RTX 4060 Ti (8GB) | 32GB RAM
Optimized for Hybrid Curriculum Learning -> Self-Play.
"""
import sys
import os

threads = "8" 
if "--threads" in sys.argv:
    idx = sys.argv.index("--threads")
    if idx + 1 < len(sys.argv):
        threads = sys.argv[idx + 1]

os.environ["OMP_NUM_THREADS"] = threads
os.environ["OPENBLAS_NUM_THREADS"] = threads
os.environ["MKL_NUM_THREADS"] = threads
os.environ["VECLIB_MAXIMUM_THREADS"] = threads
os.environ["NUMEXPR_NUM_THREADS"] = threads

import argparse
import numpy as np
import time
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import VecEnvWrapper
from mk11_env import MK11VecEnv

class SelfPlaySaveCallback(BaseCallback):
    def __init__(self, save_path: str, save_freq: int, verbose: int = 0):
        super().__init__(verbose)
        self.save_path = save_path
        self.save_freq = save_freq

    def _on_step(self) -> bool:
        if self.n_calls % self.save_freq == 0:
            temp_path = self.save_path + "_temp"
            self.model.save(temp_path)
            
            try:
                os.replace(temp_path + ".zip", self.save_path + ".zip")
                if self.verbose > 0:
                    print(f"\n[{self.save_path}] Self-play model safely updated.")
            except Exception as e:
                if self.verbose > 0:
                    print(f"\n[{self.save_path}] Save collision avoided. Skipping update.")
                    
        return True

class DashboardCallback(BaseCallback):
    def __init__(self, print_freq: int, env_wrapper, side_name: str, verbose: int = 0):
        super().__init__(verbose)
        self.print_freq = print_freq
        self.env_wrapper = env_wrapper
        self.side_name = side_name.upper()
        
    def _on_step(self) -> bool:
        # Sync the total timesteps with the hybrid pool so it knows when to switch modes
        self.env_wrapper.opp_pool.current_steps = self.num_timesteps

        if self.n_calls % self.print_freq == 0:
            wr, total_matches = self.env_wrapper.get_stats()
            
            training_progress = min(1.0, self.num_timesteps / 50_000_000)
            aptitude = 10 + (wr * 0.4) + (training_progress * 50)
            
            if aptitude < 30: rank = "Apprentice (Easy)"
            elif aptitude < 50: rank = "Kombatant (Medium)"
            elif aptitude < 70: rank = "Warrior (Hard)"
            elif aptitude < 85: rank = "Grandmaster (Pro)"
            else: rank = "Elder God (Unbeatable)"

            if total_matches == 0:
                challenge = "Gathering Data..."
            elif 40 <= wr <= 60:
                challenge = "EXCELLENT (Perfectly Matched ⚔️)"
            elif wr > 60:
                challenge = "POOR (Opponent is too weak 📉)"
            else:
                challenge = "OVERWHELMING (Opponent is dominating 💀)"

            # Check which phase the opponent pool is in
            mode = "SELF-PLAY (Neural Network)" if self.env_wrapper.opp_pool.is_self_play else "CURRICULUM (Scripted Dummy)"

            print("\n" + "═"*50)
            print(f"🥊 {self.side_name} TRAINING DASHBOARD 🥊")
            print("═"*50)
            print(f"⏱️  Total Steps  : {self.num_timesteps:,}")
            print(f"⚔️  Recent Games : {total_matches} matches played")
            print(f"🏆  Win Rate     : {wr:.1f}%")
            print(f"🤖  Opponent     : {mode}")
            print(f"🔥  Challenge    : {challenge}")
            print(f"🧠  Aptitude     : {aptitude:.1f}/100 [{rank}]")
            print("═"*50 + "\n")
            
        return True

# ==========================================
# THE HYBRID CURRICULUM OPPONENT POOL
# ==========================================
class HybridOpponentPool:
    def __init__(self, path: str, n_envs: int, switch_timestep: int, reload_every: int = 500):
        self.path = path
        self.n_envs = n_envs
        self.model = None
        self.last_mtime = 0.0
        self.call_count = 0
        self.reload_every = reload_every
        self.switch_timestep = switch_timestep
        
        self.current_steps = 0
        self.is_self_play = False
        
        # THE FIX: Give the Dummy cooldowns so it doesn't attack 60 times a second!
        self.dummy_actions = np.zeros(n_envs, dtype=np.int32)
        self.dummy_cooldowns = np.zeros(n_envs, dtype=np.int32)
        
        self._try_load()

    def _try_load(self):
        # [Keep this exactly the same]
        pass # Copy your old _try_load here

    def _scripted_predict(self, obs_batch: np.ndarray) -> np.ndarray:
        current_obs = obs_batch[:, -6:]
        norm_dist = current_obs[:, 2]
        dist = norm_dist * 2500.0 

        for i in range(self.n_envs):
            # If the dummy is currently waiting/animating, let it finish
            if self.dummy_cooldowns[i] > 0:
                self.dummy_cooldowns[i] -= 1
                self.dummy_actions[i] = 0  # <--- THE FIX: Force the dummy to release the buttons!
                continue
                
            d = dist[i]
            chance = np.random.rand()
            action = 0 # Default to Idle
            cooldown = 1 # Think for 1 frame
            
            if d > 350:
                action = 1 # Walk Forward
                if chance < 0.05: 
                    action = 48 # Bolas Projectile
                    cooldown = 60 # Rest for 1 second after throwing
            else:
                if chance < 0.30:
                    action = 15 # D1 Poke
                    cooldown = 30
                elif chance < 0.50:
                    action = 24 # F2 Heavy
                    cooldown = 45
                elif chance < 0.75:
                    action = 3 # Stand Block
                    cooldown = 10
                else:
                    action = 5 # Crouch Block
                    cooldown = 10
                    
            self.dummy_actions[i] = action
            self.dummy_cooldowns[i] = cooldown

        return self.dummy_actions

    def predict_batch(self, obs_batch: np.ndarray) -> np.ndarray:
        self.call_count += 1
        if self.current_steps >= self.switch_timestep:
            if not self.is_self_play:
                print(f"\n[!] CURRICULUM PHASE COMPLETE: Swapping Dummy for Neural Network! [!]\n")
                self.is_self_play = True

            if self.call_count % self.reload_every == 0: self._try_load()

            if self.model is not None:
                with torch.no_grad():
                    obs_t = torch.as_tensor(obs_batch, dtype=torch.float32, device="cuda")
                    actions = self.model.policy._predict(obs_t, deterministic=False)
                return actions.cpu().numpy()
        return self._scripted_predict(obs_batch)


class OpponentInjector(VecEnvWrapper):
    def __init__(self, venv: MK11VecEnv, opp_pool: HybridOpponentPool):
        super().__init__(venv)
        self.opp_pool = opp_pool
        self.episode_wins = 0
        self.episode_losses = 0

    def reset(self):
        return self.venv.reset()

    def step_async(self, actions):
        opp_obs = self.venv.get_opponent_obs()          
        opp_actions = self.opp_pool.predict_batch(opp_obs)  
        self.venv.set_opponent_actions(opp_actions)      
        self.venv.step_async(actions)

    def step_wait(self):
        obs, rewards, dones, infos = self.venv.step_wait()
        
        for i in range(len(dones)):
            if dones[i]:
                if rewards[i] > 500:
                    self.episode_wins += 1
                elif rewards[i] < -500:
                    self.episode_losses += 1
                    
        return obs, rewards, dones, infos
        
    def get_stats(self):
        total = self.episode_wins + self.episode_losses
        wr = (self.episode_wins / total * 100) if total > 0 else 50.0
        self.episode_wins = 0
        self.episode_losses = 0
        return wr, total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--side",   type=str, choices=["sz", "kollector"], required=True)
    parser.add_argument("--threads", type=str, default="8", help="CPU cores to dedicate")
    parser.add_argument("--envs",   type=int, default=1024)
    parser.add_argument("--resume", type=str, default=None)
    
    # THE FIX: Added a configurable switch threshold via the command line (Defaults to 16M)
    parser.add_argument("--switch", type=int, default=30_000_000, help="Timestep to switch to Self-Play")
    
    args = parser.parse_args()

    os.makedirs("models", exist_ok=True)

    my_save_path = f"models/{args.side}_latest"
    opp_path = "models/kollector_latest.zip" if args.side == "sz" else "models/sz_latest.zip"

    vec_env = MK11VecEnv(num_envs=args.envs, training_side=args.side)
    
    # Initialize the Hybrid Opponent
    opponent = HybridOpponentPool(opp_path, args.envs, switch_timestep=args.switch)
    wrapped = OpponentInjector(vec_env, opponent)

    policy_kwargs = dict(
        net_arch=dict(pi=[512, 512, 256, 256], vf=[512, 512, 256, 256])
    )

    self_play_callback = SelfPlaySaveCallback(
        save_path=my_save_path,
        save_freq=16384,  
        verbose=1
    )
    
    dashboard_callback = DashboardCallback(
        print_freq=4096, 
        env_wrapper=wrapped,
        side_name=args.side
    )

    print(f"[{args.side.upper()}] Hardware Init: i7-14700K | 32GB RAM | RTX 4060 Ti (8GB)")
    print(f"[{args.side.upper()}] Curriculum Swap Set to {args.switch:,} Timesteps")

    if args.resume:
        print(f"[{args.side.upper()}] Resuming from {args.resume}")
        model = PPO.load(args.resume, env=wrapped, device="cuda")
    else:
        model = PPO(
            "MlpPolicy", wrapped,
            policy_kwargs=policy_kwargs,
            verbose=0, 
            device="cuda",
            batch_size=16384,    
            n_steps=4096,        
            n_epochs=10, 
            ent_coef=0.02,
            learning_rate=0.00025,
            clip_range=0.2,
            gamma=0.995,
        )

    try:
        model.learn(total_timesteps=2_000_000_000, callback=[self_play_callback, dashboard_callback])
    except KeyboardInterrupt:
        print(f"\n[{args.side.upper()}] Interrupted!")
    finally:
        model.save(my_save_path)
        print(f"[{args.side.upper()}] Saved to {my_save_path}.zip")