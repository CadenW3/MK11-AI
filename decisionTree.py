import time
import vgamepad as vg
from test import VisionEngine

# --- CONFIG & INITIALIZATION ---
gamepad = vg.VX360Gamepad()
vision = VisionEngine()
vision.start()

FRAME = 1.0 / 60.0
BTN = vg.XUSB_BUTTON

def _reset():
    gamepad.reset()
    gamepad.update()

def block(state=True, low=False):
    """Simple block toggle."""
    _reset()
    if state:
        # Fixed the constant names here
        gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_LEFT) 
        if low: 
            gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_DOWN)
        
        gamepad.right_trigger(value=255)
    gamepad.update()

# Master list of all Kollector attack hashes
KNOWN_ATTACKS = {
    "3768540966", "607859926", "2824186958", "2122140632", "2831421598",
    "3768540965", "2357853487", "3479665097", "456944475", "3768540964",
    "3036668384", "85556008", "268592778", "3768540963", "506215777",
    "4224942067", "3437910845", "1372080832", "4217316500", "2044332179",
    "1866906029", "3728915557", "2386899317"
}

def safe_recover(frames):
    """Waits out our own attack animation. If Kollector attacks, it instantly BUFFERS a block."""
    threat_seen = False
    
    for _ in range(frames):
        if not threat_seen:
            with vision.lock:
                p2 = vision.data.get("p2")
                # If we see a known attack...
                if p2 and str(p2.get('move_hash', "0000")) in KNOWN_ATTACKS:
                    threat_seen = True
                    print("\n!!! CAUGHT LACKING! BUFFERING EMERGENCY BLOCK !!!")
                    
                    # DO NOT WAIT. Hold Block and Back down IMMEDIATELY.
                    # MK11 will queue this and block the exact millisecond recovery ends.
                    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_LEFT)
                    gamepad.right_trigger(value=255)
                    gamepad.update()
                    
        time.sleep(FRAME)
    
    # If we had to emergency block, keep holding it for a bit to absorb the hit
    if threat_seen:
        time.sleep(0.4) # Hold guard to take the impact
        _reset()
        return True
        
    return False # Animation finished, no threats seen

def attack_1():
    """Example attack: Front Punch (X/Square)"""
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()

def crouch(state=True):
    """Simple duck toggle (NO BLOCKING). Great for dodging High attacks and throws."""
    _reset()
    if state:
        gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_DOWN)
    gamepad.update()

FRAME = 1.0 / 60.0

def punish_throw_combo():
    """Double Front Punch (X, X) combo specifically for post-throw defense."""
    # First X
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 10) # Tiny gap between hits
    
    # Second X
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 25) # Recovery before next read

def punish_heavy():
    """Full 1,1,2 string (X, X, Y) for highly unsafe moves (Fatal Blows, Shotei Fury)."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 8)
    
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 8)

    gamepad.press_button(BTN.XUSB_GAMEPAD_Y)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 30)

def punish_poke():
    """Fast Down+1 (D1) poke to interrupt safe or slightly minus basic attacks."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_DOWN)
    gamepad.update()
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 18) # Quick recovery to resume blocking

def punish_ranged(right=True):
    """Teleport (Hellport: Down, Back, A) to counter projectiles from a distance."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_DOWN)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    if right:
        gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_LEFT) # Assumes P1 facing right
    else:
        gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_RIGHT) # Assumes P1 facing left
    gamepad.press_button(BTN.XUSB_GAMEPAD_A)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 40)

def offensive_y():
    """Safe single hit check (Y / Back Punch). High block advantage."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_Y)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    
    # Fast recovery because it's a single safe hit
    safe_recover(18) 

def offensive_yx():
    """Safe two-hit string (Y, X). Keeps heavy pressure on Kollector."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_Y)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()

    # Tiny gap check: If he attacks between hit 1 and 2, abort and block!
    if safe_recover(6): 
        print(">>> COMBO ABORTED: Staggering into block!")
        return

    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    
    safe_recover(22)

def offensive_yxy():
    """Full safe string (Y, X, Y). Heavy pushback and advantageous frames."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_Y)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()

    if safe_recover(6):
        return

    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()

    if safe_recover(6):
        return

    gamepad.press_button(BTN.XUSB_GAMEPAD_Y)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    
    safe_recover(25)

def offensive_spear():
    """Raw spear with open eyes during recovery."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_LEFT)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    
    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_RIGHT)
    gamepad.press_button(BTN.XUSB_GAMEPAD_X)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    
    # If we miss, wake up the millisecond Kollector tries to punish
    safe_recover(40) 

def dash_forward():
    """Quick double-tap right, ready to block instantly."""
    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_RIGHT)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    time.sleep(FRAME * 2)
    gamepad.press_button(BTN.XUSB_GAMEPAD_DPAD_RIGHT)
    gamepad.update()
    time.sleep(FRAME * 2)
    _reset()
    safe_recover(15)

# --- MAIN LOGIC GATE ---
def main():
    print(">> Bot Active. Listening for vision data...")
    last_print_time = 0
    last_hash = "0000"
    hash_start_time = time.time()
    try:
        while True:
            start_time = time.time()

            # 1. GET DATA
            with vision.lock:
                p1 = vision.data.get("p1")
                p2 = vision.data.get("p2")
            
            if not p1 or not p2:
                continue

            # 2. CALCULATE VARIABLES
            dist = abs(p1['x'] - p2['x'])
            # 'hash' here represents whatever move/state ID you're looking for
            current_hash = str(p2.get('move_hash', p2.get('action', '0000')))
            
            # --- THE DELTA TRACKER ---
            # If we see a brand new hash, start the stopwatch
            if current_hash != last_hash:
                hash_start_time = time.time()
                last_hash = current_hash
            
            # Calculate exactly how many seconds have passed since Kollector started this move
            time_elapsed = time.time() - hash_start_time
            # -------------------------
            
            # 3. YOUR CUSTOM LOGIC (The "Playground")


            # ---------------------------------------------------------

            # Front Punch block
            if current_hash == "3768540966":
                speed_coeff = 0  # Your original speed
                startup_offset = 0.1   # Your original offset
                curve_bias = 0  # The "Bend" - start very small (like 0.0000001)
                mid_range_correction = curve_bias * (dist * (1100 - dist)) 
                total_wait = (speed_coeff * dist + startup_offset) - mid_range_correction
                print(f"!!! FRONT PUNCH DETECTED - Distance: {dist:.1f} | Wait: {total_wait:.4f}")
                adjusted_wait = total_wait - time_elapsed
                time.sleep(max(0, adjusted_wait))
                block(True)
                time.sleep(0.1)
                block(False)
                print(">>> Block Released")
                _reset()
                time.sleep(0.3)
                punish_poke()
            
            # Forward Front Punch block
            if current_hash == "607859926":
                print(f"!!! FORWARD FRONT PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.175)
                block(True, low=True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Down Front Punch block
            if current_hash == "2824186958":
                print(f"!!! DOWN FRONT PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.1)
                block(True, low=True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Backward Front Punch block
            if current_hash == "2122140632":
                print(f"!!! BACKWARD FRONT PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.2)
                block(True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Up Front Punch block
            if current_hash == "2831421598":
                print(f"!!! UP FRONT PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.15)
                block(True, low=False)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Back Punch block
            if current_hash == "3768540965":
                print(f"!!! BACK PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.175)
                block(True)
                time.sleep(0.3)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Forward Back Punch block
            if current_hash == "2357853487":
                print(f"!!! FORWARD BACK PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.175)
                block(True)
                time.sleep(0.3)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Down Back Punch block
            if current_hash == "3479665097":
                print(f"!!! DOWN BACK PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.125)
                block(True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Backward Back Punch block
            if current_hash == "456944475":
                print(f"!!! BACKWARD BACK PUNCH DETECTED - Distance: {dist:.1f}")
                time.sleep(0.125)
                block(True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Front Kick block
            if current_hash == "3768540964":
                print(f"!!! FRONT KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.15)
                block(True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # ForwardFront Kick block
            if current_hash == "3036668384":
                print(f"!!! FORWARD FRONT KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.3)
                block(True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Down Front Kick block
            if current_hash == "85556008":
                print(f"!!! DOWN FRONT KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.1)
                block(True, low=True)
                time.sleep(0.15)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Backward Front Kick block
            if current_hash == "268592778":
                print(f"!!! BACKWARD FRONT KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.15)
                block(True)
                time.sleep(0.4)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Back Kick block
            if current_hash == "3768540963":
                print(f"!!! BACK KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.185)
                block(True)
                time.sleep(0.4)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()
            
            # Forward Back Kick block
            if current_hash == "506215777":
                print(f"!!! FORWARD BACK KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.225)
                block(True, low=True)
                time.sleep(0.4)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Down Back Kick block
            if current_hash == "4224942067":
                print(f"!!! DOWN BACK KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.12)
                block(True, low=True)
                time.sleep(0.4)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Backward Back Kick block
            if current_hash == "3437910845":
                print(f"!!! BACKWARD BACK KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.25)
                block(True, low=True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Up Back Kick block
            if current_hash == "1372080832":
                print(f"!!! UP KICK DETECTED - Distance: {dist:.1f}")
                time.sleep(0.1)
                block(True)
                time.sleep(0.2)
                block(False)
                print(">>> Block Released")
                time.sleep(0.3)
                punish_poke()

            # Throw defense
            if current_hash == "4217316500" or current_hash == "4217316500":
                print(f"!!! THROW DEFENSE DETECTED - Distance: {dist:.1f}")
                time.sleep(0.01)
                gamepad.press_button(BTN.XUSB_GAMEPAD_X)
                gamepad.update()
                time.sleep(FRAME * 2)
                _reset()
                punish_throw_combo()

            # ---------------------------------------------------------

            # Bola block
            if current_hash == "2044332179":
                speed_coeff = 0.001   # Your original speed
                startup_offset = 0.325   # Your original offset
                curve_bias = 0.000000445  # The "Bend" - start very small (like 0.0000001)
                mid_range_correction = curve_bias * (dist * (1100 - dist)) 
                total_wait = (speed_coeff * dist + startup_offset) - mid_range_correction
                print(f"!!! PROJECTILE DETECTED - Distance: {dist:.1f} | Wait: {total_wait:.4f}")
                time.sleep(max(0, total_wait))
                block(True)
                time.sleep(0.415)
                block(False)
                print(">>> Block Released")
                time.sleep(0.25)
                if p1['x'] < p2['x']:
                    punish_ranged(right=True)
                else:
                    punish_ranged(right=False)

            # Mace block
            elif current_hash == "1866906029":
                speed_coeff = 0.00027   # Your original speed
                startup_offset = 0.42   # Your original offset
                curve_bias = 0.000000  # The "Bend" - start very small (like 0.0000001)
                mid_range_correction = curve_bias * (dist * (1100 - dist)) 
                total_wait = (speed_coeff * dist + startup_offset) - mid_range_correction
                print(f"!!! MACE DETECTED - Distance: {dist:.1f} | Wait: {total_wait:.4f}")
                adjusted_wait = total_wait - time_elapsed
                time.sleep(max(0, adjusted_wait))
                block(True)
                time.sleep(0.415)
                block(False)
                print(">>> Block Released")
                time.sleep(0.25)
                if p1['x'] < p2['x']:
                    punish_ranged(right=True)
                else:
                    punish_ranged(right=False)

            # Shotei Fury block
            elif current_hash == "3728915557":
                speed_coeff = 0.0003   # Your original speed
                startup_offset = 0.12   # Your original offset
                curve_bias = 0.00000047  # The "Bend" - start very small (like 0.0000001)
                mid_range_correction = curve_bias * (dist * (1100 - dist)) 
                total_wait = (speed_coeff * dist + startup_offset) - mid_range_correction
                print(f"!!! SHOTEI FURY DETECTED - Distance: {dist:.1f} | Wait: {total_wait:.4f}")
                adjusted_wait = total_wait - time_elapsed
                time.sleep(max(0, adjusted_wait))
                block(True)
                time.sleep(0.8)
                block(False)
                print(">>> Block Released")
                time.sleep(0.1)
                punish_heavy()


            # ---------------------------------------------------------

            # Fatal Blow block
            elif current_hash == "2386899317":
                speed_coeff = 0.0003   # Your original speed
                startup_offset = 0.3   # Your original offset
                curve_bias = 0.000000445  # The "Bend" - start very small (like 0.0000001)
                mid_range_correction = curve_bias * (dist * (1100 - dist)) 
                total_wait = (speed_coeff * dist + startup_offset) - mid_range_correction
                print(f"!!! FATAL BLOW DETECTED - Distance: {dist:.1f} | Wait: {total_wait:.4f}")
                time.sleep(max(0, total_wait))
                block(True)
                time.sleep(0.275)
                block(False)
                print(">>> Block Released")
                time.sleep(0.1)
                punish_heavy()

            # ---------------------------------------------------------

            # ---------------------------------------------------------
            # THE SAFE STAGGER NEUTRAL LOOP (FRAME TRAPS)
            # ---------------------------------------------------------
            # else:
            #     import random
                
            #     # 1. Point Blank / Close (< 200): The Blender
            #     if dist < 200:
            #         # Randomly choose between the three safe options to confuse the opponent
            #         stagger_choice = random.choice(["Y", "YX", "YXY"])
                    
            #         if stagger_choice == "Y":
            #             print(f"--- STAGGER: [Y] Check | Dist: {dist:.1f}")
            #             offensive_y()
            #         elif stagger_choice == "YX":
            #             print(f"--- STAGGER: [Y, X] Pressure | Dist: {dist:.1f}")
            #             offensive_yx()
            #         else:
            #             print(f"--- STAGGER: [Y, X, Y] Full String | Dist: {dist:.1f}")
            #             offensive_yxy()
                        
            #     # 2. Mid Range (200 - 350): Close the gap safely
            #     elif 200 <= dist < 350:
            #         print(f"--- OFFENSE: Advancing Dash | Dist: {dist:.1f}")
            #         dash_forward()
                    
            #     # 3. Far Range (> 350): Walk them down, rarely spear
            #     else:
            #         if random.random() > 0.95: # 5% chance to throw spear
            #             print(f"--- OFFENSE: Full Screen Spear! | Dist: {dist:.1f}")
            #             offensive_spear()
            #         else:
            #             print(f"--- OFFENSE: Dash & Block | Dist: {dist:.1f}")
            #             dash_forward()
            # 4. CONSOLE OUTPUT (Keep it simple)
            # 4. CONSOLE OUTPUT (Throttled to 10 FPS to save CPU)
            if time.time() - last_print_time > 0.1:
                print(f"Dist: {dist:.0f} | P1 HP: {p1['hp']:.2f} | P2 HP: {p2['hp']:.2f} | Hash: {current_hash}    ", end='\r')
                last_print_time = time.time()

            # Maintain frame rate
            elapsed = time.time() - start_time
            if elapsed < FRAME:
                time.sleep(FRAME - elapsed)

    except KeyboardInterrupt:
        print("\n>> Shutting down.")
    finally:
        _reset()
        vision.running = False
        vision.join()

if __name__ == "__main__":
    main()