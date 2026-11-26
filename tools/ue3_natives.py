#!/usr/bin/env python3
"""Find Unreal Engine 3's native function lookup tables in a loaded Xbox 360 image.

UE3 console builds link every package's natives statically and register them through tables of
  struct FNativeFunctionLookup { const ANSICHAR* Name; Native Pointer; };   // {"execFoo", &AClass::execFoo}
one table per class, NULL-terminated, and a per-package table of {class name, table}. On the 360 a member function
pointer of a single-inheritance class is the code address, so each entry is two big-endian words: a pointer to the
ASCII name and a code address.

usage: ue3_natives.py <image.bin> <image base> <code base> <code size> <out.tsv>
"""
import re
import struct
import sys
from collections import defaultdict

img_path, base, code_base, code_size, out_path = sys.argv[1], *(int(x, 0) for x in sys.argv[2:5]), sys.argv[5]
data = open(img_path, "rb").read()
end = base + len(data)
code_end = code_base + code_size


def word(addr):
    o = addr - base
    return struct.unpack_from(">I", data, o)[0] if 0 <= o <= len(data) - 4 else None


def cstr(addr, limit=256):
    o = addr - base
    if not (0 <= o < len(data)):
        return None
    e = data.find(b"\0", o, o + limit)
    if e < 0:
        return None
    s = data[o:e]
    try:
        return s.decode("ascii")
    except UnicodeDecodeError:
        return None


# Every printable ASCII string outside the code, by address, and every UTF-16BE one (this build's TCHAR is wide:
# its native names are TEXT("execFoo")).
strings = {}
for m in re.finditer(rb"[\x20-\x7e]{3,200}\0", data):
    a = base + m.start()
    if code_base <= a < code_end:
        continue
    strings[a] = m.group()[:-1].decode("ascii")
wide = 0
for m in re.finditer(rb"(?:\x00[\x20-\x7e]){2,200}\x00\x00", data):
    if m.start() % 2:
        continue
    a = base + m.start()
    if code_base <= a < code_end:
        continue
    strings[a] = m.group()[:-2].decode("utf-16-be")
    wide += 1
print(f"{len(strings)} strings outside the code ({wide} UTF-16)")

# Words that point at a string, followed by a word in the code: candidate lookup entries.
entries = {}
for o in range(0, len(data) - 8, 4):
    a = base + o
    if code_base <= a < code_end:
        continue
    p, f = struct.unpack_from(">II", data, o)
    if p in strings and code_base <= f < code_end and f % 4 == 0:
        entries[a] = (strings[p], f)
print(f"{len(entries)} (string, code) pairs")

# This build's MAP_NATIVE names an entry TEXT("int") TEXT(#cls) TEXT(#func): "intAActorexecSpawn".
NATIVE = re.compile(r"^int([A-Z]\w*?)(exec\w+)$")

# Tables: runs of consecutive pairs (8-byte stride) ending at a {0, 0} pair, with at least one native name.
tables = []
seen = set()
for a in sorted(entries):
    if a in seen or (a - 8) in entries:
        continue
    run = []
    b = a
    while b in entries:
        run.append((b, *entries[b]))
        seen.add(b)
        b += 8
    terminated = word(b) == 0 and word(b + 4) == 0
    if any(NATIVE.match(n) for _, n, _ in run):
        tables.append((a, run, terminated))
print(f"{len(tables)} tables with native names ({sum(len(r) for _, r, _ in tables)} entries)")

names = defaultdict(set)
classes = defaultdict(int)
with open(out_path, "w") as out:
    out.write("# address\tclass\tfunction\ttable\n")
    for start, run, terminated in tables:
        for at, n, f in run:
            m = NATIVE.match(n)
            if not m:
                continue
            cls, fn = m.groups()
            names[f].add(f"{cls}::{fn}")
            classes[cls] += 1
            out.write(f"0x{f:08X}\t{cls}\t{fn}\t0x{start:08X}\n")
print(f"{len(names)} distinct code addresses named ({sum(len(v) for v in names.values())} names, "
      f"{len(classes)} classes); written to {out_path}")
shared = sum(1 for v in names.values() if len(v) > 1)
print(f"{shared} addresses carry more than one name (identical code folded by the linker)")
for cls, n in sorted(classes.items(), key=lambda kv: -kv[1])[:12]:
    print(f"  {cls}: {n}")
