#!/usr/bin/env python3
"""Gears of War 2 decompilation: disassemble guest PowerPC code from the dumped image (capstone).

    disasm.py <image.bin> <address> [instructions, default 64] [--calls]

--calls prints only the branches-and-link with the four instructions before each (how the arguments are set up).
"""
import struct
import sys

import capstone

BASE = 0x82000000


def main():
    data = open(sys.argv[1], "rb").read()
    at = int(sys.argv[2], 16)
    count = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 64
    calls_only = "--calls" in sys.argv
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    lines = [f"{i.address:08X}  {i.mnemonic:8s} {i.op_str}" for i in
             md.disasm(data[at - BASE:at - BASE + 4 * count], at)]
    if not calls_only:
        print("\n".join(lines))
        return
    for n, line in enumerate(lines):
        if " bl " in f" {line.split(None, 1)[1]}" or line.split()[1] in ("bl", "bctrl"):
            print("\n".join(lines[max(0, n - 4):n + 1]))
            print("--")


if __name__ == "__main__":
    main()
