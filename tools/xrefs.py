#!/usr/bin/env python3
"""Gears of War 2 decompilation: who loads an address, and who calls a function (PowerPC code in a loaded image).

    xrefs.py <image.bin> <register.cpp> <symbols.tsv|-> data <addr>...    code that builds the address (lis + addi/ori)
    xrefs.py <image.bin> <register.cpp> <symbols.tsv|-> calls <addr>...   bl / b to the address
    xrefs.py <image.bin> <register.cpp> <symbols.tsv|-> consts <func>...  every address a function builds, in order

The image is the codegen's REX_DUMP_IMAGE (base 0x82000000, code 0x82220000-0x82F5D8AC); function entries come from
the generated register file (SetFunction lines). Names from decomp/symbols.tsv when given. A constant counts when a
lis and an addi/ori from that register build it with no branch in between (the usual MSVC Xenon pattern).
"""
import bisect
import re
import struct
import sys

BASE, CODE, CODE_END = 0x82000000, 0x82220000, 0x82220000 + 0xD3D8AC


def load(img, reg, syms):
    data = open(img, "rb").read()
    starts = sorted(int(m.group(1), 16) for m in re.finditer(r"SetFunction\(0x([0-9A-Fa-f]{8})", open(reg).read()))
    names = {}
    if syms != "-":
        for line in open(syms, encoding="utf-8"):
            if not line.startswith("#"):
                c = line.rstrip("\n").split("\t")
                names[int(c[0], 16)] = c[1]
    return data, starts, names


def func_of(starts, a):
    i = bisect.bisect_right(starts, a) - 1
    return starts[i] if i >= 0 else 0


def label(names, f):
    return f"sub_{f:08X}" + (f" [{names[f]}]" if f in names else "")


def constants(data, start, end):
    """(instruction address, value) of every lis + addi/ori constant in [start, end)."""
    out = []
    hi = {}
    for o in range(start - BASE, end - BASE, 4):
        w = struct.unpack_from(">I", data, o)[0]
        op = w >> 26
        if op == 15 and ((w >> 16) & 31) == 0:  # lis rD,imm
            hi[(w >> 21) & 31] = ((w & 0xFFFF) << 16) & 0xFFFFFFFF
        elif op in (14, 24):  # addi rD,rA,imm / ori rA,rS,imm
            ra = (w >> 16) & 31 if op == 14 else (w >> 21) & 31
            rd = (w >> 21) & 31 if op == 14 else (w >> 16) & 31
            if ra in hi and ra != 0:
                imm = w & 0xFFFF
                v = (hi[ra] + (imm - 0x10000 if (op == 14 and imm & 0x8000) else imm)) & 0xFFFFFFFF
                out.append((BASE + o, v))
                if rd != ra:
                    hi.pop(rd, None)
        elif op == 18 or (op == 19 and ((w >> 1) & 0x3FF) in (16, 528)):  # b/bl, bclr/bcctr
            hi.clear()
        elif op in (32, 34, 40, 42) and ((w >> 21) & 31) in hi:  # lwz/lbz/lhz/lha into a tracked reg: gone
            hi.pop((w >> 21) & 31, None)
    return out


def main():
    img, reg, syms, mode = sys.argv[1:5]
    targets = [int(a, 16) for a in sys.argv[5:]]
    data, starts, names = load(img, reg, syms)
    if mode == "consts":
        for f in targets:
            i = bisect.bisect_right(starts, f)
            end = starts[i] if i < len(starts) else CODE_END
            print(f"== {label(names, f)}")
            for at, v in constants(data, f, end):
                kind = "code " + label(names, v) if v in names or (CODE <= v < CODE_END and v in set(starts)) else ""
                print(f"   {at:08X}: {v:08X} {kind}")
        return
    want = set(targets)
    hits = {t: [] for t in targets}
    if mode == "data":
        for at, v in constants(data, CODE, CODE_END):
            if v in want:
                hits[v].append(at)
    elif mode == "calls":
        for o in range(CODE - BASE, CODE_END - BASE, 4):
            w = struct.unpack_from(">I", data, o)[0]
            if w >> 26 == 18:
                li = w & 0x03FFFFFC
                if li & 0x02000000:
                    li -= 0x04000000
                t = (li if (w & 2) else BASE + o + li) & 0xFFFFFFFF
                if t in want:
                    hits[t].append(BASE + o)
    for t in targets:
        print(f"== {t:08X} {label(names, t) if t in names else ''}: {len(hits[t])} references")
        for at in hits[t]:
            print(f"   {at:08X} in {label(names, func_of(starts, at))}")


if __name__ == "__main__":
    main()
