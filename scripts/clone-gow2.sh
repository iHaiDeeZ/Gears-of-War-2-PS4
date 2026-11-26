#!/usr/bin/env bash
# Fetch the sources the PS4 build needs into ~/gow2-build/src (run in WSL), at the commits in patches/BASE.txt:
#   src/gow2          santiquiroz/gears-of-war-2-pc-port, branch ps4, with patches/gow2-ps4.patch (ps4/: the app and
#                     the passes)
#   src/sdk           nx-mod/rexglue-sdk-nx with iHaiDeeZ/MP3-PS4's patches/sdk-ps4.patch and
#                     iHaiDeeZ/Vigilante-8-Arcade-PS4's patches/sdk-vig8.patch (the V8 port's PS4 SDK, committed as the
#                     base), branch gow2 with patches/sdk-gow2.patch
#   src/rexglue-sdk   rexglue/rexglue-sdk v0.10.0: the third-party sources sdk/ does not carry (and the host code
#                     generator's tree); ~/mp3-build/src/rexglue-sdk is used when there
# Re-running keeps existing checkouts (GOW2_SOURCE_RESET=1 starts gow2 and sdk over). If github.com is out of reach
# from WSL, clone on Windows (git clone --mirror) and point GOW2_MIRROR at the folder holding <repo>.git mirrors.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
S="$HOME/gow2-build/src"
base() { awk -v k="$1" '$1 == k { print $2 }' "$HERE/patches/BASE.txt"; }
commit() { git -C "$1" add -A && git -C "$1" -c user.name=gow2 -c user.email=gow2@localhost commit -q -m "$2"; }
url() {  # a GitHub repository, or its mirror in GOW2_MIRROR
    if [ -n "${GOW2_MIRROR:-}" ] && [ -d "$GOW2_MIRROR/$2.git" ]; then echo "$GOW2_MIRROR/$2.git"; else echo "https://github.com/$1/$2"; fi
}
raw() {  # one file of a GitHub repository at a commit (the local checkout's copy when it is that commit)
    local local_repo="$1" repo="$2" commit="$3" path="$4" out="$5"
    if [ -f "$local_repo/$path" ] && [ "$(git -C "$local_repo" rev-parse --short=7 HEAD 2>/dev/null)" = "${commit:0:7}" ]; then
        cp "$local_repo/$path" "$out"
    else
        curl -fsSL "https://raw.githubusercontent.com/iHaiDeeZ/$repo/$commit/$path" -o "$out"
    fi
}
mkdir -p "$S" "$HOME/gow2-build/logs"
ln -sfn "$HERE" "$HOME/gow2-build/proj"

if [ "${GOW2_SOURCE_RESET:-0}" = 1 ]; then rm -rf "$S/gow2" "$S/sdk"; fi

if [ ! -e "$S/rexglue-sdk" ]; then
    if [ -d "$HOME/mp3-build/src/rexglue-sdk/.git" ] \
        && [ "$(git -C "$HOME/mp3-build/src/rexglue-sdk" rev-parse HEAD)" = "$(base rexglue-sdk)" ]; then
        ln -s "$HOME/mp3-build/src/rexglue-sdk" "$S/rexglue-sdk"
    else
        git clone -q --recursive "$(url rexglue rexglue-sdk)" "$S/rexglue-sdk"
        git -C "$S/rexglue-sdk" checkout -q "$(base rexglue-sdk)"
        git -C "$S/rexglue-sdk" submodule update -q --init --recursive
    fi
fi

if [ ! -d "$S/sdk/.git" ]; then
    git clone -q "$(url nx-mod rexglue-sdk-nx)" "$S/sdk"
    git -C "$S/sdk" checkout -q -b ps4 "$(base rexglue-sdk-nx)"
    raw "$HERE/../MP3" MP3-PS4 "$(base MP3-PS4)" patches/sdk-ps4.patch "$S/sdk-ps4.patch"
    git -C "$S/sdk" apply --whitespace=nowarn "$S/sdk-ps4.patch"
    commit "$S/sdk" "PS4 port (MP3-PS4)"
    raw "$HERE/../Vigilante 8" Vigilante-8-Arcade-PS4 "$(base Vigilante-8-Arcade-PS4)" patches/sdk-vig8.patch "$S/sdk-vig8.patch"
    git -C "$S/sdk" checkout -q -b gow2
    git -C "$S/sdk" apply --whitespace=nowarn "$S/sdk-vig8.patch"
    commit "$S/sdk" "Base: the vig8 branch working tree (V8A v00.11 SDK)"
    [ -s "$HERE/patches/sdk-gow2.patch" ] && git -C "$S/sdk" apply --whitespace=nowarn "$HERE/patches/sdk-gow2.patch"
fi

if [ ! -d "$S/gow2/.git" ]; then
    git clone -q "$(url santiquiroz gears-of-war-2-pc-port)" "$S/gow2"
    git -C "$S/gow2" checkout -q -b ps4 "$(base gow2-pc-port)"
    git -C "$S/gow2" apply --whitespace=nowarn "$HERE/patches/gow2-ps4.patch"
    # The quick menu's fonts (Lato, SIL Open Font License), kept beside the patches.
    mkdir -p "$S/gow2/ps4/fonts"
    cp "$HERE/patches/fonts/"* "$S/gow2/ps4/fonts/"
fi
echo "sources ready in $S"
