import os
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.env_util import make_vec_env

# Import your custom engine
from mk11_env import MK11AdvancedEnv

if __name__ == "__main__":
    print("1. Initializing and Verifying the MK11 Simulation...")
    # Verify the environment rules on a single instance first
    dummy_env = MK11AdvancedEnv()
    check_env(dummy_env, warn=True)
    print("Environment check passed!")

    print("\n2. Vectorizing 16 Environments for the RTX 4060 Ti...")
    # This is the magic line that unleashes your GPU
    vec_env = make_vec_env(MK11AdvancedEnv, n_envs=16)
    
    print("\n3. Building the PPO Neural Network Brain...")
    model = PPO(
        "MlpPolicy", 
        vec_env, 
        verbose=1, 
        device="cuda",          # Force PyTorch to use the GPU
        learning_rate=0.0003,
        n_steps=2048,
        batch_size=1024,        # Massively increased batch size for GPU efficiency
        gamma=0.99 
    )

    # --- THE TRAINING PHASE ---
    training_frames = 100_000_000 
    print(f"\n4. Starting Training for {training_frames} frames...")
    
    model.learn(total_timesteps=training_frames)

    # Save the trained brain
    os.makedirs("models", exist_ok=True)
    model.save("models/subzero_mk11_master")
    print("\nTraining Complete. AI Brain saved to 'models/subzero_mk11_master.zip'")

    # ==========================================
    # EVALUATION: WATCH THE AI PLAY
    # ==========================================
    print("\n5. Loading the trained brain for a test match...")
    del model 
    del vec_env
    
    trained_model = PPO.load("models/subzero_mk11_master")
    
    # We must use a single environment for the evaluation printout
    eval_env = MK11AdvancedEnv()
    obs, info = eval_env.reset()
    
    print("MATCH START: Sub-Zero (AI) vs Kollector (Dummy)")
    total_reward = 0
    
    for frame in range(1000): 
        action, _states = trained_model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = eval_env.step(action)
        total_reward += reward
        
        # Extract the integer if it returns an array
        extracted_action = int(action)
        
        if reward > 20: # Lowered the threshold slightly based on our new reward math
            print(f"Frame {frame}: Massive hit! AI used Action {extracted_action} and scored {reward:.1f} points.")
        elif reward < -20:
            print(f"Frame {frame}: AI took heavy damage or whiffed badly! Penalty: {reward:.1f}")

        if terminated or truncated:
            print(f"\nMatch Over at Frame {frame}!")
            print(f"Total Match Reward: {total_reward:.1f}")
            break