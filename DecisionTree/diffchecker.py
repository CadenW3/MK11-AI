"""
diff_scan.py — Find the real action state offset.

Timer-based: 5-second countdowns give you time to pick up the controller.
Captures CONTINUOUSLY for 2-3 seconds per phase, so it catches values
mid-animation, not just a single instant.

Usage: python diff_scan.py p2
"""

import time
import struct
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

target = sys.argv[1] if len(sys.argv) > 1 else "p2"
char_ptr = mem.p2_char_ptr if target == "p2" else mem.p1_char_ptr
info_ptr = mem.p2_info_ptr if target == "p2" else mem.p1_info_ptr
print(f"Scanning {target.upper()} char_ptr: {hex(char_ptr)}")
print(f"Scanning {target.upper()} info_ptr: {hex(info_ptr)}\n")

SCAN_RANGE = 0x1200
INNER_RANGE = 0x400
FRAME = 1.0 / 60.0


def read_region_uint(base, size):
    vals = {}
    try:
        raw = mem.pm.read_bytes(base, size)
        for off in range(0, size - 4, 4):
            vals[off] = struct.unpack('<I', raw[off:off + 4])[0]
    except:
        pass
    return vals


def find_pointers(base, size):
    ptrs = {}
    try:
        raw = mem.pm.read_bytes(base, size)
        for off in range(0, size - 8, 8):
            val = struct.unpack('<Q', raw[off:off + 8])[0]
            if 0x10000000000 < val < 0x6FFFFFFFFFF:
                ptrs[off] = val
    except:
        pass
    return ptrs


def snapshot():
    snap = {}
    snap['char'] = read_region_uint(char_ptr, SCAN_RANGE)
    ptrs = find_pointers(char_ptr, SCAN_RANGE)
    for off, ptr_val in ptrs.items():
        key = f"ptr@{hex(off)}"
        inner = read_region_uint(ptr_val, INNER_RANGE)
        if inner:
            snap[key] = inner
    snap['info'] = read_region_uint(info_ptr, 0x200)
    info_ptrs = find_pointers(info_ptr, 0x200)
    for off, ptr_val in info_ptrs.items():
        key = f"iptr@{hex(off)}"
        inner = read_region_uint(ptr_val, INNER_RANGE)
        if inner:
            snap[key] = inner
    return snap


def multi_snapshot(duration_sec=2.0):
    """Take many snapshots over a duration, collect all unique values per offset."""
    all_snaps = []
    end = time.time() + duration_sec
    while time.time() < end:
        all_snaps.append(snapshot())
        time.sleep(FRAME * 2)
    merged = {}
    for snap in all_snaps:
        for region, vals in snap.items():
            if region not in merged:
                merged[region] = {}
            for off, val in vals.items():
                if off not in merged[region]:
                    merged[region][off] = set()
                merged[region][off].add(val)
    return merged


def countdown(msg, seconds=5):
    print(f"\n>> {msg}")
    for i in range(seconds, 0, -1):
        print(f"   {i}...")
        time.sleep(1)
    print("   CAPTURING...")


def diff_merged(merged_a, merged_b):
    diffs = []
    all_regions = set(merged_a.keys()) | set(merged_b.keys())
    for region in sorted(all_regions):
        a = merged_a.get(region, {})
        b = merged_b.get(region, {})
        for off in sorted(set(a.keys()) & set(b.keys())):
            va, vb = a[off], b[off]
            if va & vb:
                continue
            if all(v > 1000000 for v in va) and all(v > 1000000 for v in vb):
                continue
            if all(v > 0x10000000 for v in va) and all(v > 0x10000000 for v in vb):
                continue
            va_s = ",".join(str(v) for v in sorted(va)[:5])
            vb_s = ",".join(str(v) for v in sorted(vb)[:5])
            if len(va) > 5: va_s += "..."
            if len(vb) > 5: vb_s += "..."
            diffs.append((region, off, va_s, vb_s))
    return diffs


def print_diffs(diffs, la, lb):
    if not diffs:
        print("  No differences found.")
        return
    print(f"  {len(diffs)} changed offsets:\n")
    print(f"  {'Region':<30} | {'Offset':>8} | {la:>20} | {lb:>20}")
    print("  " + "-" * 85)
    for r, o, va, vb in diffs:
        print(f"  {r[:29]:<30} | {hex(o):>8} | {va:>20} | {vb:>20}")


print("=" * 70)
print("3 phases. Use your controller during each capture window.")
print("Each phase: 5s countdown → 2-3s capture.")
print("=" * 70)

# IDLE
countdown("PHASE 1: Stand IDLE — hands off controller", 5)
m_idle = multi_snapshot(2.0)
print(f"  Got {sum(len(v) for v in m_idle.values())} values\n")

# ATTACK
countdown("PHASE 2: SPAM ATTACKS — mash buttons, do combos, specials", 5)
m_atk = multi_snapshot(3.0)
print(f"  Got {sum(len(v) for v in m_atk.values())} values\n")

# BLOCK
countdown("PHASE 3: HOLD BLOCK — hold back", 5)
m_blk = multi_snapshot(2.0)
print(f"  Got {sum(len(v) for v in m_blk.values())} values\n")

print("=" * 70)
print("IDLE → ATTACK:")
print("=" * 70)
d_ia = diff_merged(m_idle, m_atk)
print_diffs(d_ia, "IDLE", "ATTACK")

print("\n" + "=" * 70)
print("IDLE → BLOCK:")
print("=" * 70)
d_ib = diff_merged(m_idle, m_blk)
print_diffs(d_ib, "IDLE", "BLOCK")

print("\n" + "=" * 70)
print("ATTACK → BLOCK:")
print("=" * 70)
d_ab = diff_merged(m_atk, m_blk)
print_diffs(d_ab, "ATTACK", "BLOCK")

# Best candidates
ia_k = {(r, o) for r, o, _, _ in d_ia}
ib_k = {(r, o) for r, o, _, _ in d_ib}
ab_k = {(r, o) for r, o, _, _ in d_ab}
best = ia_k & ib_k & ab_k

print("\n" + "=" * 70)
print("BEST CANDIDATES (different in ALL three comparisons):")
print("=" * 70)
if best:
    ia_m = {(r, o): (a, b) for r, o, a, b in d_ia}
    ib_m = {(r, o): (a, b) for r, o, a, b in d_ib}
    print(f"\n  {len(best)} candidates:\n")
    print(f"  {'Region':<30} | {'Offset':>8} | {'IDLE':>15} | {'ATTACK':>15} | {'BLOCK':>15}")
    print("  " + "-" * 95)
    for r, o in sorted(best):
        iv, av = ia_m.get((r, o), ("?", "?"))
        _, bv = ib_m.get((r, o), ("?", "?"))
        print(f"  {r[:29]:<30} | {hex(o):>8} | {iv:>15} | {av:>15} | {bv:>15}")
else:
    print("  None found. Check individual diffs above.")

print("\nSend me this output and I'll wire it into the bot.")