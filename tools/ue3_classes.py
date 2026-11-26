#!/usr/bin/env python3
"""Name Unreal Engine 3's class registration functions in a loaded Xbox 360 image.

IMPLEMENT_CLASS(TClass) makes TClass::GetPrivateStaticClassTClass(Package), which builds the UClass with
  ::new UClass(EC_StaticConstructor, sizeof(TClass), flags, cast flags, TEXT(#TClass)+1, Package, config name,
               object flags, (void(*)(void*))&TClass::InternalConstructor, (void(UObject::*)())&TClass::StaticConstructor)
so the function loads the address of the wide string L"AActor" plus one character (the class name without its prefix),
and two code addresses that go to the stack as the 9th and 10th arguments (after the object flags). The constants are
built with lis/addi (or lis/ori) pairs.

usage: ue3_classes.py <image.bin> <image base> <code base> <code size> <register.cpp> <out.tsv>
"""
import bisect
import re
import struct
import sys

import capstone

img_path, base, code_base, code_size = sys.argv[1], *(int(x, 0) for x in sys.argv[2:5])
reg_path, out_path = sys.argv[5], sys.argv[6]
data = open(img_path, "rb").read()
code_end = code_base + code_size

starts = sorted(int(m.group(1), 16) for m in re.finditer(r"SetFunction\(0x([0-9A-Fa-f]{8})", open(reg_path).read()))
print(f"{len(starts)} functions")

# Wide strings (UTF-16BE, 2-aligned) outside the code: address -> text.
wide = {}
for m in re.finditer(rb"(?:\x00[\x20-\x7e]){2,200}\x00\x00", data):
    if m.start() % 2:
        continue
    a = base + m.start()
    if code_base <= a < code_end:
        continue
    wide[a] = m.group()[:-2].decode("utf-16-be")
CLASS = re.compile(r"^[AUF][A-Z][A-Za-z0-9_]*$")
# The address the class registration loads: the string's second character.
name_at = {a + 2: s for a, s in wide.items() if CLASS.match(s)}
print(f"{len(wide)} wide strings, {len(name_at)} that look like class names")

md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
md.skipdata = True


def scan(start, end):
    """The constants a function builds, in order: (kind, value, stack offset or None)."""
    hi = {}       # register -> value from lis
    val = {}      # register -> full constant
    found = []
    o0, o1 = start - base, end - base
    for ins in md.disasm(data[o0:o1], start):
        m, ops = ins.mnemonic, ins.op_str.replace(" ", "").split(",")
        try:
            if m == "lis":
                r = ops[0]
                hi[r] = (int(ops[1], 0) & 0xFFFF) << 16
                val.pop(r, None)
            elif m in ("addi", "ori") and len(ops) == 3 and (ops[1] in val or ops[1] in hi):
                imm = int(ops[2], 0)
                # addi from a full constant (the class name's "+1 character": addi r8,r11,2), else from a lis.
                src = val[ops[1]] if ops[1] in val else hi[ops[1]]
                v = (src | (imm & 0xFFFF)) if m == "ori" else (src + imm)
                v &= 0xFFFFFFFF
                val[ops[0]] = v
                hi.pop(ops[0], None)
                found.append(("const", v, ops[0], None))
            elif m == "stw" and len(ops) == 2 and ops[0] in val:
                mm = re.match(r"(-?\w+)\((r\d+)\)", ops[1])
                if mm and mm.group(2) == "r1":
                    found.append(("stack", val[ops[0]], ops[0], int(mm.group(1), 0)))
            elif m in ("bl", "b", "blr", "bctrl", "bctr"):
                # A call clobbers the volatile registers.
                for r in [f"r{i}" for i in range(0, 13)]:
                    hi.pop(r, None)
                    val.pop(r, None)
            else:
                if ops and ops[0] in val and m not in ("stw", "stwu", "cmpw", "cmplw", "cmpwi", "cmplwi", "mtctr"):
                    val.pop(ops[0], None)
                    hi.pop(ops[0], None)
        except (ValueError, IndexError):
            continue
    return found


rows = []
names = {}
for i, s in enumerate(starts):
    e = starts[i + 1] if i + 1 < len(starts) else code_end
    if e - s > 4096:
        continue
    consts = scan(s, e)
    cls_names = [name_at[v] for k, v, r, off in consts if k == "const" and v in name_at]
    if len(cls_names) != 1:
        continue
    code_on_stack = sorted((off, v) for k, v, r, off in consts
                           if k == "stack" and code_base <= v < code_end and v in set(starts))
    if len(code_on_stack) < 2:
        continue
    cls = cls_names[0]
    # Stack arguments in order: InternalConstructor, StaticConstructor, StaticInitializer (UE3's UClass constructor
    # takes the class's static initializer after its static constructor). The two static ones are often UObject's
    # empty defaults, folded by the linker into one address shared by many classes.
    internal, static = code_on_stack[0][1], code_on_stack[1][1]
    init = code_on_stack[2][1] if len(code_on_stack) > 2 else 0
    rows.append((cls, s, internal, static, init))
    names[s] = f"{cls}::GetPrivateStaticClass{cls}"
    names.setdefault(internal, f"{cls}::InternalConstructor")

with open(out_path, "w") as out:
    out.write("# class\tGetPrivateStaticClass\tInternalConstructor\tStaticConstructor\tStaticInitializer\n")
    for cls, s, i_, st, ini in sorted(rows):
        out.write(f"{cls}\t0x{s:08X}\t0x{i_:08X}\t0x{st:08X}\t0x{ini:08X}\n")
print(f"{len(rows)} classes; {len(names)} functions named; written to {out_path}")
for r in sorted(rows)[:5]:
    print("  ", r[0], " ".join(f"0x{x:08X}" for x in r[1:]))
