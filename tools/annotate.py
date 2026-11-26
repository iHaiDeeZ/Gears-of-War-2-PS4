#!/usr/bin/env python3
"""Names the recompiled functions in a profile, crash log or freeze report with the decompilation's symbol table.

Every sub_XXXXXXXX (also __imp__sub_ / __fast__sub_) that decomp/symbols.tsv names gets its name after it:
    sub_824A2EA0  ->  sub_824A2EA0 [UGameEngine::Tick]
An address inside a named function (a guest return address, "lr 0x824A2F10") is not resolved: only entries.

usage: annotate.py <symbols.tsv> [file ...]      (stdin when no file; writes to stdout)
"""
import re
import sys


def load(path):
    names = {}
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t")
        names[int(cols[0], 16)] = cols[1]
    return names


def main():
    names = load(sys.argv[1])
    pat = re.compile(r"\b((?:__imp__|__fast__)?sub_([0-9A-Fa-f]{8}))\b")

    def sub(m):
        n = names.get(int(m.group(2), 16))
        return f"{m.group(1)} [{n}]" if n else m.group(1)

    files = sys.argv[2:] or ["-"]
    for f in files:
        fh = sys.stdin if f == "-" else open(f, encoding="utf-8", errors="replace")
        for line in fh:
            sys.stdout.write(pat.sub(sub, line))


if __name__ == "__main__":
    main()
