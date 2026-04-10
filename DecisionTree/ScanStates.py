"""
scan_states.py — Run this while playing against the bot/opponent.
Stand idle for a few seconds, then attack, then block, then jump.
Look at which columns change for each action.

The goal: find which offset = "opponent is in attack animation"
so the bot can block reactively based on animation state, not raw inputs.
"""

import time
import sys
from DMA import MK11Memory

mem = MK11Memory()

print("Waiting for match lock...")
while True:
    state = mem.get_state()
    if state:
        break
    time.sleep(0.1)
print("Locked.\n")

# Track which player to watch (P2 = opponent by default)
target = sys.argv[1] if len(sys.argv) > 1 else "p2"

print(f"Watching {target.upper()} — do these actions in order:")
print("  1. Stand IDLE for 3 seconds")
print("  2. Do a POKE (D1) and hold")
print("  3. Do a STRING (4,4,3)")
print("  4. BLOCK (hold back)")
print("  5. JUMP")
print()
print(f"{'frame':>5} | {'state':>10} | {'sub':>10} | {'vm_frame':>10} | {'move':>10} | {'flags':>10} | {'stun_a':>8} | {'stun_b':>8} | {'stun_c':>10} | {'inp':>6} | {'inp_buf':>8} | {'hp':>6} | {'x':>8} | {'y':>8}")
print("-" * 160)

FRAME = 1.0 / 60.0
frame = 0
prev_state = None

try:
    while True:
        state = mem.get_state()
        if not state:
            time.sleep(0.1)
            continue

        p = state[target]
        
        # Only print when something changes (to reduce noise)
        cur = (p['state'], p['vm_sub'], p['vm_frame'], p['vm_move'], p['vm_flags'])
        changed = cur != prev_state
        prev_state = cur
        
        if changed or frame % 15 == 0:  # print on change or every 15 frames
            marker = " <<< CHANGED" if changed else ""
            print(
                f"{frame:>5} | "
                f"{p['state']:>10} | "
                f"{p['vm_sub']:>10} | "
                f"{p['vm_frame']:>10} | "
                f"{p['vm_move']:>10} | "
                f"{p['vm_flags']:>10} | "
                f"{p['stun_a']:>8.3f} | "
                f"{p['stun_b']:>8.3f} | "
                f"{p['stun_c']:>10} | "
                f"{p['inputs']:>6} | "
                f"{p['inputs_buf']:>8} | "
                f"{p['hp']:.3f} | "
                f"{p['x']:>8.1f} | "
                f"{p['y']:>8.1f}"
                f"{marker}"
            )

        frame += 1
        time.sleep(FRAME)

except KeyboardInterrupt:
    print("\nDone.")