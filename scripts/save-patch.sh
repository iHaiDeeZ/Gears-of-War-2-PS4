#!/usr/bin/env bash
# Export the PS4 port's changes from the WSL checkouts into patches/ (run in WSL):
#   patches/gow2-ps4.patch   ~/gow2-build/src/gow2 against BASE.txt's gow2-pc-port commit (ps4/: the app and the
#                            passes)
#   patches/sdk-gow2.patch   ~/gow2-build/src/sdk against the V8 port's PS4 SDK (rexglue-sdk-nx at BASE.txt's commit
#                            with MP3-PS4's sdk-ps4.patch and Vigilante-8-Arcade-PS4's sdk-vig8.patch: the gow2
#                            branch's first commit)
# Neither checkout's index is touched (a temporary index each), nothing is committed. The game's files and what is made
# from them (generated code, image.bin, decomp tables) live outside both trees.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
V="$HOME/gow2-build"
SRC="${GOW2_SRC:-$V/src/gow2}"
SDK="${GOW2_SDK:-$V/src/sdk}"
base() { awk -v k="$1" '$1 == k { print $2 }' "$HERE/patches/BASE.txt"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export GIT_INDEX_FILE="$TMP/gow2-index"
git -C "$SRC" read-tree "$(base gow2-pc-port)"
# Python's caches go first (naming an ignored path in the pathspec makes git add fail). The quick menu's fonts
# (ps4/fonts, Lato, OFL) are kept as files in patches/fonts, not in the patch.
find "$SRC/ps4" -name __pycache__ -type d -prune -exec rm -rf {} +
git -C "$SRC" add -A -- . ':(exclude)ps4/fonts'
git -C "$SRC" diff --cached --binary "$(base gow2-pc-port)" > "$HERE/patches/gow2-ps4.patch"
mkdir -p "$HERE/patches/fonts"
cp "$SRC/ps4/fonts/"* "$HERE/patches/fonts/"

export GIT_INDEX_FILE="$TMP/sdk-index"
SDK_BASE="$(git -C "$SDK" log --format=%H --grep='^Base: the vig8 branch working tree' -1)"
git -C "$SDK" read-tree "$SDK_BASE"
# thirdparty/ is left out: build-gow2.sh fills it from rexglue-sdk v0.10.0 (and patches/ffmpeg), as MP3's build does.
git -C "$SDK" add -A -- . ':(exclude)thirdparty'
git -C "$SDK" diff --cached --binary "$SDK_BASE" -- . ':(exclude)thirdparty' > "$HERE/patches/sdk-gow2.patch"
unset GIT_INDEX_FILE

for p in gow2-ps4 sdk-gow2; do
    echo "patches/$p.patch: $(grep -c '^diff --git' "$HERE/patches/$p.patch" || true) files, $(du -h "$HERE/patches/$p.patch" | cut -f1)"
done
