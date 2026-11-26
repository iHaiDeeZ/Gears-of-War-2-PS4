#!/usr/bin/env python3
"""gow2-ps4: a hot-function link order from burst profiles (lld's --symbol-ordering-file).

    make_order.py <out.txt> <profile_N.txt> <the ELF that ran it> [<profile> <elf>]...

The eboot's text is ~50 MB (the recompiled game is 450 files of one section per function, -ffunction-sections), and
a busy frame runs code from all over it: the Jaguar's 32 KB instruction cache, its 2 MB L2 and its TLBs keep missing.
Laying the sampled functions next to each other (in the order of their samples) packs the code a frame runs into a few
MB. Every frame of every sampled stack counts (a function's own samples weigh 4, the time it is on the stack 1); the
recompiled functions bring their entry wrappers along (sub_X with __fast__sub_X and __imp__sub_X). Names are the
link names (llvm-nm without demangling), so the file works for later builds as long as the functions keep their names;
lld skips names it does not find (--no-warn-symbol-ordering).
"""
import bisect
import collections
import re
import subprocess
import sys

NM = "llvm-nm-21"


def symbols(elf):
    """Sorted (address, size, name) of the ELF's functions, and .text's start (the profile's addresses are relative)."""
    out = subprocess.run([NM, "--defined-only", "--print-size", "--numeric-sort", elf], capture_output=True,
                         text=True).stdout
    funcs, text_start = [], 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == "__text_start":
            text_start = int(parts[0], 16)
        if len(parts) != 4 or parts[2] not in "tTwW":
            continue
        funcs.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
    funcs.sort()
    return funcs, text_start


def weigh(profile, elf, weights):
    funcs, text_start = symbols(elf)
    starts = [f[0] for f in funcs]
    misses = 0
    for line in open(profile, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(\d+)\s+(.*)", line)
        if not m or "elf 0x" not in m.group(2):
            continue
        count = int(m.group(1))
        frames = [f.strip() for f in m.group(2).split("<")]
        if frames and frames[0].endswith(" wait"):
            continue  # a thread blocked in the kernel: its stack is not running
        seen = set()
        for depth, frame in enumerate(frames):
            fm = re.match(r"elf (0x[0-9a-f]+)", frame)
            if not fm:
                continue
            a = int(fm.group(1), 16) + text_start
            i = bisect.bisect_right(starts, a) - 1
            if i < 0 or a >= funcs[i][0] + max(funcs[i][1], 1) + 64:
                misses += 1
                continue
            name = funcs[i][2]
            w = count * (4 if depth == 0 else 1)
            if name in seen and depth:
                continue  # recursion: once a stack
            seen.add(name)
            weights[name] += w
    return misses


def main():
    if len(sys.argv) < 4 or len(sys.argv) % 2:
        sys.exit(__doc__)
    out = sys.argv[1]
    weights = collections.Counter()
    for profile, elf in zip(sys.argv[2::2], sys.argv[3::2]):
        misses = weigh(profile, elf, weights)
        print(f"{profile}: {len(weights)} functions so far ({misses} addresses outside any symbol)")
    order, listed = [], set()
    for name, _ in weights.most_common():
        m = re.fullmatch(r"(?:__fast__|__imp__)?(sub_[0-9A-F]{8})", name)
        group = [name] if not m else [f"__fast__{m.group(1)}", f"__imp__{m.group(1)}", m.group(1)]
        for n in group:
            if n not in listed:
                listed.add(n)
                order.append(n)
    with open(out, "w", newline="\n") as f:
        f.write("\n".join(order) + "\n")
    print(f"{out}: {len(order)} symbols ({len(weights)} sampled functions)")


if __name__ == "__main__":
    main()
