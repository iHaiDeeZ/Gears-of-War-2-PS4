#!/usr/bin/env python3
"""Gears of War 2 decompilation: the engine's SystemSettings fields, from the loader's on-stack table.

FSystemSettings' loader (sub_82350278) fills a table on its stack before it reads the ini: pairs of
{TCHAR* key name, field address = this + offset}. Following lis/addi/mr and the stores to r1 gives each key's field
offset in the FSystemSettings object; the key names are the UTF-16 strings the pointers point at.

usage: settings_table.py <image.bin> <register.cpp> [function, default 0x82350278]
"""
import bisect
import re
import struct
import sys

import capstone

BASE = 0x82000000


def wstr(data, a):
    o = a - BASE
    if not (0 <= o < len(data)):
        return None
    e = o
    while e + 1 < len(data) and not (data[e] == 0 and data[e + 1] == 0):
        e += 2
    try:
        s = data[o:e].decode("utf-16-be")
    except UnicodeDecodeError:
        return None
    return s if s.isprintable() and s else None


def main():
    data = open(sys.argv[1], "rb").read()
    starts = sorted(int(m.group(1), 16) for m in re.finditer(r"SetFunction\(0x([0-9A-Fa-f]{8})",
                                                             open(sys.argv[2]).read()))
    f = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x82350278
    e = starts[bisect.bisect_right(starts, f)]
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    regs = {"r3": ("this", 0)}  # value: ("const", v) or ("this", offset)
    stack = {}
    for ins in md.disasm(data[f - BASE:e - BASE], f):
        m, ops = ins.mnemonic, ins.op_str.replace(" ", "").split(",")
        try:
            if m == "lis":
                regs[ops[0]] = ("const", (int(ops[1], 0) << 16) & 0xFFFFFFFF)
            elif m == "addi" and ops[1] in regs:
                kind, v = regs[ops[1]]
                regs[ops[0]] = (kind, (v + int(ops[2], 0)) & 0xFFFFFFFF if kind == "const" else v + int(ops[2], 0))
            elif m == "mr":
                if ops[1] in regs:
                    regs[ops[0]] = regs[ops[1]]
                else:
                    regs.pop(ops[0], None)
            elif m == "stw" and ops[0] in regs:
                mm = re.match(r"(-?\w+)\(r1\)", ops[1])
                if mm:
                    stack[int(mm.group(1), 0)] = regs[ops[0]]
            elif m in ("bl", "bctrl"):
                # __savegprlr_N / __restgprlr_N (0x82A93xxx) only save registers; a real call clobbers the volatile
                # ones (r0, r3-r12) and leaves r1 and the non-volatiles.
                target = int(ops[0], 0) if m == "bl" else 0
                if not (0x82A93000 <= target < 0x82A94000):
                    for r in ["r0"] + [f"r{i}" for i in range(3, 13)]:
                        regs.pop(r, None)
            elif ops and re.fullmatch(r"r\d+", ops[0]) and m not in ("stw", "stb", "sth", "std", "cmpwi", "cmplwi",
                                                                      "cmpw", "cmplw"):
                regs.pop(ops[0], None)
        except (ValueError, IndexError):
            continue
    # Pairs: a name pointer followed by a field pointer 4 bytes above it.
    rows = []
    for off in sorted(stack):
        kind, v = stack[off]
        if kind == "const" and (off + 4) in stack and stack[off + 4][0] == "this":
            name = wstr(data, v)
            if name:
                rows.append((stack[off + 4][1], name, off))
    print(f"# FSystemSettings fields from sub_{f:08X}'s table: offset, key (stack slot)")
    for field, name, off in sorted(rows):
        print(f"0x{field:03X}\t{name}\t(r1+0x{off:X})")
    print(f"# {len(rows)} keys")


if __name__ == "__main__":
    main()
