#!/usr/bin/env python3
"""Gears of War 2 decompilation: code that reads or writes a global's field (PowerPC loads/stores at a fixed address).

    field_readers.py <image.bin> <register.cpp> <symbols.tsv|-> <addr>...

A register counts as holding a constant after lis (high half) and lis + addi/ori (the whole address), as xrefs.py
tracks them; a load or store through it with a displacement that lands on one of the addresses is a hit. Branches
and calls forget every register (the MSVC Xenon code rebuilds addresses after them).
"""
import bisect
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
from xrefs import BASE, CODE, CODE_END, load, func_of, label  # noqa: E402

LOADS = {32: "lwz", 34: "lbz", 40: "lhz", 42: "lha", 48: "lfs", 50: "lfd"}
STORES = {36: "stw", 38: "stb", 44: "sth", 52: "stfs", 54: "stfd"}


def scan(data, targets):
    want = set(targets)
    hits = {t: [] for t in targets}
    val = {}
    for o in range(CODE - BASE, CODE_END - BASE, 4):
        w = struct.unpack_from(">I", data, o)[0]
        op = w >> 26
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 15 and ra == 0:  # lis
            val[rd] = (imm << 16) & 0xFFFFFFFF
            continue
        if op == 14 and ra != 0 and ra in val:  # addi
            val[rd] = (val[ra] + simm) & 0xFFFFFFFF
            continue
        if op == 24 and rd in val:  # ori rA,rS,imm (rS = bits 21-25)
            val[ra] = val[rd] | imm
            continue
        if op in LOADS or op in STORES:
            if ra in val:
                a = (val[ra] + simm) & 0xFFFFFFFF
                if a in want:
                    kind = LOADS.get(op) or STORES.get(op)
                    hits[a].append((BASE + o, kind))
            if op in LOADS and op < 48:
                val.pop(rd, None)
            continue
        if op == 18 or op == 16 or (op == 19 and ((w >> 1) & 0x3FF) in (16, 528)):
            val.clear()
            continue
        # Anything else that writes rD (integer ops): forget it. Rough, errs towards fewer hits.
        if op in (7, 8, 10, 11, 12, 13, 20, 21, 23, 25, 26, 27, 28, 29, 31):
            val.pop(rd if op not in (20, 21, 23, 24, 25, 26, 27, 28, 29) else ra, None)
            if op == 31:
                val.pop(ra, None)
    return hits


def main():
    img, reg, syms = sys.argv[1:4]
    targets = [int(a, 16) for a in sys.argv[4:]]
    data, starts, names = load(img, reg, syms)
    hits = scan(data, targets)
    for t in targets:
        print(f"== {t:08X}: {len(hits[t])} accesses")
        for at, kind in hits[t]:
            print(f"   {at:08X} {kind:4s} in {label(names, func_of(starts, at))}")


if __name__ == "__main__":
    main()
