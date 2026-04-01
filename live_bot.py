import time
import cv2
import mss
import numpy as np
import vgamepad as vg
from stable_baselines3 import PPO
from ultralytics import YOLO

print("Starting MK11 AI Pipeline...")
gamepad = vg.VX360Gamepad()
print("Virtual Controller Connected.")

try:
    brain = PPO.load("models/subzero_mk11_master")
    eyes = YOLO("best.pt") 
    print("Brain and Eyes Loaded successfully.")
    
    print("Warming up GPU...")
    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    eyes(dummy_frame, device=0, imgsz=640, conf=0.6, verbose=False)
    brain.predict(np.zeros(8, dtype=np.float32))
except Exception as e:
    print(f"Error loading AI models: {e}")

sct = mss.mss()
monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}

def extract_health_and_meter(frame):
    """Uses OpenCV HSV masking to count the yellow pixels in the health bars."""
    sz_crop = frame[40:80, 140:860]   
    k_crop = frame[40:80, 1060:1780]  

    sz_hsv = cv2.cvtColor(sz_crop, cv2.COLOR_BGR2HSV)
    k_hsv = cv2.cvtColor(k_crop, cv2.COLOR_BGR2HSV)

    lower_yellow = np.array([15, 100, 100])
    upper_yellow = np.array([45, 255, 255])

    sz_mask = cv2.inRange(sz_hsv, lower_yellow, upper_yellow)
    k_mask = cv2.inRange(k_hsv, lower_yellow, upper_yellow)

    sz_pixels = cv2.countNonZero(sz_mask)
    k_pixels = cv2.countNonZero(k_mask)

    max_pixels = sz_crop.shape[0] * sz_crop.shape[1]
    
    sz_health = min(1000.0, (sz_pixels / max_pixels) * 1000.0 * 1.75)
    k_health = min(1000.0, (k_pixels / max_pixels) * 1000.0 * 1.75)

    if sz_health < 50: sz_health = 1000.0
    if k_health < 50: k_health = 1000.0

    return sz_health, k_health, 0.0, 0.0

def execute_action(action, is_facing_right):
    """Executes the AI's chosen action with animation cooldowns."""
    gamepad.reset() 
    
    forward_btn = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT if is_facing_right else vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT
    backward_btn = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT if is_facing_right else vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT

    is_attack = False

    if action == 1: gamepad.press_button(button=forward_btn)
    elif action == 2: gamepad.press_button(button=backward_btn)
    elif action == 3: gamepad.right_trigger_float(value_float=1.0)
    elif action == 4: gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
    elif action == 5: 
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
        gamepad.right_trigger_float(value_float=1.0)
    elif action == 6: 
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
        is_attack = True
    elif action == 7: 
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
        is_attack = True
    elif action == 8: 
        gamepad.press_button(button=backward_btn)
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        is_attack = True
    elif action == 9: 
        gamepad.press_button(button=forward_btn)
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
        is_attack = True
    elif action == 11: 
        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
        is_attack = True
    
    gamepad.update() 

    if is_attack:
        time.sleep(0.05) 
        gamepad.reset()  
        gamepad.update() 
        time.sleep(0.4) 

print("\nReady. Switch to MK11 'Press Any Button' title screen NOW!")
print("Connecting virtual controller as Player 1...")

for _ in range(5):
    gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    gamepad.update()
    time.sleep(0.1)
    gamepad.reset()
    gamepad.update()
    time.sleep(0.9)

print("\n--- LIVE FEED STARTED ---")
frame_count = 0
last_sz_x, last_sz_y = 200.0, 500.0
last_k_x, last_k_y = 1500.0, 500.0

while True:
    start_time = time.time()
    
    img = np.array(sct.grab(monitor))
    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    results = eyes(frame, device=0, imgsz=640, conf=0.6, verbose=False)
    
    found_sz, found_k = False, False
    sz_x, sz_y, k_x, k_y = 0.0, 0.0, 0.0, 0.0
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            y_center = float(box.xywh[0][1])
            if y_center < 300: 
                continue
                
            x_center = float(box.xywh[0][0])
            class_id = int(box.cls[0])
            
            if class_id == 1 and not found_sz: 
                sz_x, sz_y = x_center, y_center
                found_sz = True
            elif class_id == 0 and not found_k: 
                k_x, k_y = x_center, y_center
                found_k = True

    if not found_sz: sz_x, sz_y = last_sz_x, last_sz_y
    if not found_k: k_x, k_y = last_k_x, last_k_y
    
    last_sz_x, last_sz_y = sz_x, sz_y
    last_k_x, last_k_y = k_x, k_y

    # --- THE COORDINATE SYNCHRONIZATION FIX ---
    real_distance_x = k_x - sz_x
    is_facing_right = real_distance_x >= 0
    abs_real_distance = abs(real_distance_x)

    # 150px is the physical collision limit in MK11
    padded_distance = max(0.0, abs_real_distance - 150.0)
    scale_factor = 40.0 / 350.0 
    
    # MATCH THE MATRIX: Tell the AI it is at X=200 (Safe zone), not X=0 (Corner panic)
    sim_sz_x = 200.0
    sim_k_x = 200.0 + (padded_distance * scale_factor)
    
    sim_sz_y = 0.0
    sim_k_y = 0.0

    # Ensure health is seen as a full 1000 for the test
    sz_health, k_health, sz_meter, k_meter = extract_health_and_meter(frame)
    
    obs = np.array([sim_sz_x, sim_k_x, sim_sz_y, sim_k_y, sz_health, k_health, 0.0, 0.0], dtype=np.float32)
    
    action, _states = brain.predict(obs, deterministic=True)
    extracted_action = int(action)
    
    execute_action(extracted_action, is_facing_right)
    
    frame_count += 1
    if frame_count % 30 == 0:
        print(f"Dist: {padded_distance:.1f}px -> AI Thinks: {sim_k_x - 500:.1f}u || Action: {extracted_action}")
    
    process_time = time.time() - start_time
    if process_time < (1.0 / 60.0):
        time.sleep((1.0 / 60.0) - process_time)