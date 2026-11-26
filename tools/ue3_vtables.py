#!/usr/bin/env python3
"""Each UE3 class's vtable, from its InternalConstructor (classes.tsv from ue3_classes.py), and the virtual functions
attributed to the class that introduces them.

InternalConstructor(void* X) is `new((EInternal*)X) TClass;`: the constructor (inlined or called) stores the base
classes' vtables at [this+0] first and the class's own last. The last store of a data-section constant to offset 0 of
the object, following calls one level deep, is the class's vtable. A vtable is the run of words from there that are
function entries.

A virtual function is named after the class with the fewest slots among the vtables holding it at that slot (the
class closest to the base that has it), as <Class>::vf<slot>.

usage: ue3_vtables.py <image.bin> <image base> <code base> <code size> <register.cpp> <classes.tsv> <out.tsv>
"""
import re
import struct
import sys
from collections import defaultdict

import capstone

img_path, base, code_base, code_size = sys.argv[1], *(int(x, 0) for x in sys.argv[2:5])
reg_path, classes_path, out_path = sys.argv[5:8]
data = open(img_path, "rb").read()
code_end = code_base + code_size
starts = sorted(int(m.group(1), 16) for m in re.finditer(r"SetFunction\(0x([0-9A-Fa-f]{8})", open(reg_path).read()))
start_set = set(starts)
import bisect


def fend(s):
    i = bisect.bisect_right(starts, s)
    return starts[i] if i < len(starts) else code_end


def word(a):
    o = a - base
    return struct.unpack_from(">I", data, o)[0] if 0 <= o <= len(data) - 4 else None


md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
md.skipdata = True


def vtable_stores(s, depth=0, this_regs=("r3",)):
    """Data constants stored to 0(this) in order, following direct calls with this in r3 one level deep."""
    e = fend(s)
    if e - s > 8192:
        return []
    hi, val = {}, {}
    this = set(this_regs)
    out = []
    for ins in md.disasm(data[s - base:e - base], s):
        m, ops = ins.mnemonic, ins.op_str.replace(" ", "").split(",")
        try:
            if m == "lis":
                hi[ops[0]] = (int(ops[1], 0) & 0xFFFF) << 16
                val.pop(ops[0], None)
                this.discard(ops[0])
            elif m in ("addi", "ori") and len(ops) == 3 and (ops[1] in val or ops[1] in hi):
                imm = int(ops[2], 0)
                src = val[ops[1]] if ops[1] in val else hi[ops[1]]
                val[ops[0]] = ((src | (imm & 0xFFFF)) if m == "ori" else (src + imm)) & 0xFFFFFFFF
                hi.pop(ops[0], None)
                this.discard(ops[0])
            elif m == "mr" and len(ops) == 2:
                if ops[1] in this:
                    this.add(ops[0])
                else:
                    this.discard(ops[0])
                if ops[1] in val:
                    val[ops[0]] = val[ops[1]]
                else:
                    val.pop(ops[0], None)
            elif m == "stw" and len(ops) == 2 and ops[0] in val:
                mm = re.match(r"(-?\w+)\((r\d+)\)", ops[1])
                if mm and int(mm.group(1), 0) == 0 and mm.group(2) in this:
                    v = val[ops[0]]
                    if not (code_base <= v < code_end):
                        out.append(v)
            elif m == "bl" and depth == 0 and "r3" in this:
                t = int(ops[0], 0)
                if t in start_set:
                    out.extend(vtable_stores(t, depth + 1))
                for r in [f"r{i}" for i in range(0, 13)]:
                    hi.pop(r, None)
                    val.pop(r, None)
                this = {r for r in this if r not in [f"r{i}" for i in range(0, 13)]}
            elif m in ("bl", "bctrl"):
                for r in [f"r{i}" for i in range(0, 13)]:
                    hi.pop(r, None)
                    val.pop(r, None)
                this = {r for r in this if r not in [f"r{i}" for i in range(0, 13)]}
            elif m == "blr":
                break
            elif ops and ops[0].startswith("r") and m not in ("stw", "stwu", "std", "stb", "sth", "cmpw", "cmplw",
                                                              "cmpwi", "cmplwi", "mtctr", "mtlr", "stfs", "stfd"):
                val.pop(ops[0], None)
                hi.pop(ops[0], None)
                this.discard(ops[0])
        except (ValueError, IndexError):
            continue
    return out


known_starts = []  # every vtable any constructor stores: vtables sit back to back, so each one ends at the next


def vtable_slots(v):
    slots = []
    a = v
    nxt = known_starts[bisect.bisect_right(known_starts, v)] if bisect.bisect_right(known_starts, v) < len(
        known_starts) else 1 << 32
    while a < nxt:
        w = word(a)
        if w is None or w not in start_set:
            break
        slots.append(w)
        a += 4
    return slots


classes = []
for line in open(classes_path):
    if line.startswith("#"):
        continue
    cls, gpsc, internal, static, init = line.split("\t")[:5]
    classes.append((cls, int(internal, 16)))

all_stores = {}
for cls, internal in classes:
    all_stores[cls] = vtable_stores(internal)
stored = {v for st in all_stores.values() for v in st}
print(f"{len(stored)} distinct vtables stored by the UE3 constructors")


def loaded_tables():
    """Every data address the code builds with lis + addi/ori whose first word is a function entry: the vtables of
    every class (FArchive, FTickableObject, ... too, not only UObjects), which bound the ones next to them."""
    found = set()
    code = data[code_base - base:code_end - base]
    los = {}
    for o in range(0, len(code), 4):
        w = struct.unpack_from(">I", code, o)[0]
        op = w >> 26
        if op == 15 and ((w >> 16) & 31) == 0:  # lis rD, imm
            los[(w >> 21) & 31] = ((w & 0xFFFF) << 16) & 0xFFFFFFFF
        elif op in (14, 24):  # addi / ori rD, rA, imm
            ra = (w >> 16) & 31 if op == 14 else (w >> 21) & 31
            rd = (w >> 21) & 31 if op == 14 else (w >> 16) & 31
            if ra in los:
                imm = w & 0xFFFF
                v = (los[ra] + (imm - 0x10000 if (op == 14 and imm & 0x8000) else imm)) & 0xFFFFFFFF
                if not (code_base <= v < code_end) and base <= v < base + len(data) - 4 and v % 4 == 0:
                    if word(v) in start_set and word(v + 4) in start_set:
                        found.add(v)
                los.pop(rd, None)
        elif op == 18:  # b/bl: a new block, forget
            los.clear()
    return found


loaded = loaded_tables()
known_starts = sorted(stored | loaded)
print(f"{len(loaded)} vtable-like addresses loaded by the code; {len(known_starts)} boundaries")
vt = {}
for cls, internal in classes:
    stores = all_stores[cls]
    if not stores:
        continue
    v = stores[-1]
    slots = vtable_slots(v)
    if len(slots) >= 4:
        vt[cls] = (v, slots)
print(f"{len(vt)} of {len(classes)} classes with a vtable")

# Attribute each (slot, function) to the class with the fewest slots holding it.
owner = {}
for cls, (v, slots) in vt.items():
    for i, f in enumerate(slots):
        key = (i, f)
        if key not in owner or len(slots) < len(vt[owner[key]][1]) or (
                len(slots) == len(vt[owner[key]][1]) and cls < owner[key]):
            owner[key] = cls
names = {}
for (i, f), cls in owner.items():
    names.setdefault(f, f"{cls}::vf{i}")

with open(out_path, "w") as out:
    out.write("# class\tvtable\tslots\n")
    for cls, (v, slots) in sorted(vt.items()):
        out.write(f"{cls}\t0x{v:08X}\t{len(slots)}\n")
with open(out_path.replace(".tsv", "_functions.tsv"), "w") as out:
    out.write("# address\tname\n")
    for f, n in sorted(names.items()):
        out.write(f"0x{f:08X}\t{n}\n")
sizes = sorted(len(s) for _, s in vt.values())
print(f"{len(names)} virtual functions attributed; slots per vtable {sizes[0]}..{sizes[-1]} "
      f"(median {sizes[len(sizes) // 2]})")
for c in ("UObject", "AActor", "APawn", "AGearPawn", "UGameEngine"):
    if c in vt:
        print(f"  {c}: vtable 0x{vt[c][0]:08X}, {len(vt[c][1])} slots")
