#!/usr/bin/env python3
"""gow2-ps4: every sample of a burst profile, by function (the named profile lists only its biggest stacks).

    self_time.py <profile_N.txt> <the ELF that ran it> <thread name part> [--top N] [--inclusive]

Self time: the stack's first frame in the eboot (a kernel wait at the top counts as "(waiting)"). With --inclusive,
the share of samples each function is anywhere on the stack. Names are link names from llvm-nm (recompiled guest
functions are __fast__sub_XXXXXXXX / __imp__sub_XXXXXXXX, the SDK's are mangled C++).
"""
import collections
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
from make_order import symbols  # noqa: E402
import bisect  # noqa: E402


def main():
    profile, elf, want = sys.argv[1:4]
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 30
    inclusive = "--inclusive" in sys.argv
    funcs, text_start = symbols(elf)
    starts = [f[0] for f in funcs]

    def name_of(a):
        i = bisect.bisect_right(starts, a + text_start) - 1
        return funcs[i][2] if i >= 0 else f"?{a:#x}"

    counts = collections.Counter()
    total = 0
    on = False
    for line in open(profile, encoding="utf-8", errors="replace"):
        if line.startswith("thread "):
            on = want in line
            continue
        if not on:
            continue
        m = re.match(r"\s*(\d+)\s+(.*)", line)
        if not m:
            continue
        n = int(m.group(1))
        frames = [f.strip() for f in m.group(2).split("<")]
        total += n
        if frames[0].endswith(" wait"):
            counts["(waiting in the kernel)"] += n
            continue
        if inclusive:
            seen = set()
            for f in frames:
                fm = re.match(r"elf (0x[0-9a-f]+)", f)
                if fm:
                    nm = name_of(int(fm.group(1), 16))
                    if nm not in seen:
                        seen.add(nm)
                        counts[nm] += n
            continue
        fm = re.match(r"elf (0x[0-9a-f]+)", frames[0])
        counts[name_of(int(fm.group(1), 16)) if fm else frames[0].split("+")[0]] += n
    print(f"{want}: {total} samples ({'inclusive' if inclusive else 'self'})")
    for nm, n in counts.most_common(top):
        print(f"  {100.0 * n / max(total, 1):5.1f}%  {nm[:120]}")


if __name__ == "__main__":
    main()
