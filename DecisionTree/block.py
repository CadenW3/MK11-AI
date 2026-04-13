"""
block_test_v2.py — Test all possible block methods

MK11 uses a DEDICATED BLOCK BUTTON (RT / R2), NOT hold-back.
The opponent's input stream shows BLCK (bit 32768) when blocking.

vgamepad triggers are analog — use gamepad.right_trigger(255).

This script tests RT alone, RT+back, and RT+down+back.
"""

import time
import vgamepad as vg
from DMA import VisionEngine

gamepad = vg.VX360Gamepad()
FRAME = 1.0 / 60.0

BTN   = vg.XUSB_BUTTON
DOWN  = BTN.XUSB_GAMEPAD_DPAD_DOWN
LEFT  = BTN.XUSB_GAMEPAD_DPAD_LEFT
RIGHT = BTN.XUSB_GAMEPAD_DPAD_RIGHT

vision = VisionEngine()
vision.start()

print(">> Waiting for match lock...")
while not vision.ready:
    time.sleep(0.1)
print(">> Locked.\n")
print(">> BLOCK TEST v2: Using RT (Right Trigger) as block button")
print(">> Stand next to opponent and let them hit you.\n")

frame = 0
try:
    while True:
        state = vision.get_state()
        if not state:
            time.sleep(0.01)
            continue

        p1, p2 = state["p1"], state["p2"]

        # Direction away from opponent
        if p1['x'] < p2['x']:
            back = LEFT
        else:
            back = RIGHT

        # ── BLOCK: RT (right trigger) + hold back ──
        gamepad.reset()
        gamepad.press_button(back)       # hold back direction
        gamepad.right_trigger(255)       # RT = block button (full press)
        gamepad.update()

        if frame % 30 == 0:
            dist = abs(p1['x'] - p2['x'])
            back_name = "LEFT" if back == LEFT else "RIGHT"
            print(
                f"Frame:{frame:>5} | "
                f"HP:{p1['hp']*1000:>4.0f} | "
                f"Dist:{dist:>5.0f} | "
                f"Holding: RT + {back_name}"
            )

        frame += 1
        time.sleep(FRAME)

except KeyboardInterrupt:
    print("\n>> Test over.")
finally:
    gamepad.reset()
    gamepad.update()
    vision.running = False
    vision.join()