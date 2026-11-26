#!/usr/bin/env bash
# Build Gears of War 2 (Xbox 360 retail disc, title 4D53082D) for the PS4 (ps4-kit, x86-64 Jaguar). Run in WSL:
#   scripts/build-gow2.sh host       the host code generator (ReXGlue v0.10.0 with patches/host/), once
#   scripts/build-gow2.sh codegen    the game's C++ from your default.xex, then the PC port's fixes and the PS4 passes
#   scripts/build-gow2.sh app        the eboot (game code + SDK + its Xenos GPU on Vulkan + RADV)
#   scripts/build-gow2.sh pkg        out/GOW2-vXX.YY.pkg (GOW2_VERSION=00.01); GOW2_PKG_GAME=1 puts your game inside
#                                    (one file, ~6.5 GB), else the game is read from /data/GOW2/game on the console
# The sources come from scripts/clone-gow2.sh.
#
# The Vigilante 8 port's way (iHaiDeeZ/Vigilante-8-Arcade-PS4), on the Gears of War 2 PC port
# (santiquiroz/gears-of-war-2-pc-port, BSD-3-Clause): its codegen manifest and function hints, its generated-code
# fixes (jump tables and unresolved branches, xenia-canary's game patches as switches); the game's PowerPC code
# recompiled to C++ by ReXGlue v0.10.0's code generator and built for the Jaguar with ps4-kit's clang 21; the runtime
# is the V8 port's PS4 SDK (rexglue-sdk-nx + MP3's PS4 layer + V8's command processor work); the game's command ring
# drawn by the SDK's Xenia-derived Xenos emulation on its Vulkan back end, on the kit's RADV.
#
#   ~/gow2-build/src/gow2          gears-of-war-2-pc-port, branch ps4 (ps4/: the PS4 app; ps4/tools: the passes)
#   ~/gow2-build/src/sdk           the PS4 SDK, branch gow2 (the V8 port's SDK + Gears of War 2's changes)
#   ~/gow2-build/game              your extracted disc (default.xex, GearGame/ ...), US/EU retail 0.0.0.5/0.0.0.6
set -euo pipefail
source "$HOME/ps4-kit/toolchain/env.sh"
V="$HOME/gow2-build"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${GOW2_SRC:-$V/src/gow2}"
SDK="${GOW2_SDK:-$V/src/sdk}"
UP="${GOW2_REXGLUE_SDK:-$V/src/rexglue-sdk}"
GAME="${GOW2_GAME:-$V/game}"
CG="${GOW2_CODEGEN:-$V/codegen}"
# The host code generator: ReXGlue v0.10.0 with MP3-PS4's dump-image patch and SDL headless (patches/host/), built by
# "host" below, as the V8 port builds it. The PC port's generator (923c1a5) is v0.10.0 + 9 commits, none in the
# generator. A V8 port's build of it is taken when this one has none.
REXGLUE="${GOW2_REXGLUE:-$V/src/rexglue-host/out/linux-amd64/rexglue}"
if [ ! -x "$REXGLUE" ] && [ -z "${GOW2_REXGLUE:-}" ] && [ -x "$HOME/vig8-build/src/rexglue-host/out/linux-amd64/rexglue" ]; then
    REXGLUE="$HOME/vig8-build/src/rexglue-host/out/linux-amd64/rexglue"
fi
TOOLS="$SRC/ps4/tools"
PCTOOLS="$SRC/tools"
mkdir -p "$V/logs"

if [ ! -f "$SDK/thirdparty/fmt/CMakeLists.txt" ]; then
    rsync -a --ignore-existing --exclude=.git "$UP/thirdparty/" "$SDK/thirdparty/"
fi
# The PS4's FFmpeg configuration (from the MGR port): config.h picks config_ps4_x86_64.h for __PS4__.
for f in config.h config_ps4_x86_64.h; do
    cmp -s "$HERE/patches/ffmpeg/$f" "$SDK/thirdparty/FFmpeg/$f" || cp "$HERE/patches/ffmpeg/$f" "$SDK/thirdparty/FFmpeg/$f"
done

case "${1:-}" in
host)
    H="$V/src/rexglue-host"
    if [ ! -d "$H" ]; then
        # Without the repository's own .git (1.2 GB); the submodules' .git files stay (the SDK's CMake checks them).
        rsync -a --exclude=/.git "$UP/" "$H/"
        for p in "$HERE"/patches/host/*.patch; do
            (cd "$H" && patch -p1 --forward --quiet < "$p")
        done
    fi
    # The SDK's ui library wants x11-xcb and wayland-client (pkg-config) even with SDL headless: libx11-xcb-dev and
    # libwayland-dev, installed or unpacked into host-deps/root (scripts/host-deps.sh, no root needed).
    HD="$V/host-deps/root"
    [ -f "$HD/usr/lib/x86_64-linux-gnu/pkgconfig/x11-xcb.pc" ] || bash "$HERE/scripts/host-deps.sh"
    export PKG_CONFIG_PATH="$HD/usr/lib/x86_64-linux-gnu/pkgconfig:$HD/usr/share/pkgconfig"
    cmake -S "$H" -B "$H/out/host" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang-21 -DCMAKE_CXX_COMPILER=clang++-21 \
        -DCMAKE_C_FLAGS=-march=x86-64-v2 -DCMAKE_CXX_FLAGS=-march=x86-64-v2 \
        -DCMAKE_SHARED_LINKER_FLAGS="-L$HD/usr/lib/x86_64-linux-gnu" -DCMAKE_EXE_LINKER_FLAGS="-L$HD/usr/lib/x86_64-linux-gnu" \
        -DREXGLUE_USE_VULKAN=ON -DREXGLUE_ENABLE_TRACY=OFF -DREXGLUE_SDL_HEADLESS=ON \
        > "$V/logs/configure-host.log" 2>&1 || { tail -40 "$V/logs/configure-host.log"; exit 1; }
    ninja -C "$H/out/host" rexglue > "$V/logs/build-host.log" 2>&1 \
        || { grep -E "error:|FAILED" "$V/logs/build-host.log" | head -40; exit 1; }
    echo "host built: $V/src/rexglue-host/out/linux-amd64/rexglue"
    ;;
codegen)
    [ -x "$REXGLUE" ] || { echo "no host code generator at $REXGLUE (run: scripts/build-gow2.sh host)" >&2; exit 1; }
    [ -f "$GAME/default.xex" ] || { echo "no $GAME/default.xex (extract your disc there)" >&2; exit 1; }
    [ -f "$GAME/default.xexp" ] && { echo "$GAME/default.xexp: the port is for the executable without a title update" >&2; exit 1; }
    mkdir -p "$CG/game" "$CG/hints"
    cmp -s "$GAME/default.xex" "$CG/game/default.xex" || cp "$GAME/default.xex" "$CG/game/default.xex"
    for f in "$SRC"/hints/*.toml; do
        cmp -s "$f" "$CG/hints/$(basename "$f")" || cp "$f" "$CG/hints/"
    done
    # The PC port's manifest without its *_as_local options: patch_local_regs.py keeps the guest registers in host
    # locals itself, with a whole-program analysis (the PC port's localize_fix.py is the other way to the same end);
    # plus ps4/codegen/names.toml (names for functions the PS4 sources hook, when there are any).
    python3 -I - "$SRC/gow2_manifest.toml" "$SRC/ps4/codegen/names.toml" "$CG/gow2_manifest.toml" <<'PY'
import os, re, sys
src, extra, out = sys.argv[1:]
text = re.sub(r'^(ctr|xer|reserved|cr|non_argument|non_volatile)_as_local = [^\n]*\n', '', open(src).read(), flags=re.M)
if os.path.isfile(extra):
    names = open(extra).read()
    for addr in re.findall(r'^\[entrypoint\.functions\.(0x[0-9A-Fa-f]+)\]', names, re.M):
        # The PC manifest may list it as a bare hint (0x... = {}): the named table replaces it.
        text = re.sub(rf'^{addr} = [^\n]*\n', '', text, flags=re.M | re.I)
    text = text.rstrip() + '\n\n' + names
try:
    if open(out).read() == text:
        sys.exit(0)
except OSError:
    pass
open(out, 'w').write(text)
PY
    if grep -qE '_as_local = ' "$CG/gow2_manifest.toml"; then echo "manifest: an *_as_local option is left" >&2; exit 1; fi
    # A name the SDK already defines as __imp__<name> would replace the game's function with that stub.
    for n in $(sed -n 's/^name = "\([A-Za-z_0-9]*\)".*/\1/p' "$CG/gow2_manifest.toml"); do
        case "$n" in sub_*) continue ;; esac
        if grep -rqE "__imp__$n\b" "$SDK/src" "$SDK/include"; then
            echo "codegen: the SDK already defines __imp__$n; rename it in ps4/codegen/names.toml" >&2; exit 1
        fi
    done
    # Generated and patched in a staging folder, then only the files whose text changed are copied over generated/
    # (the others keep their dates, so Ninja rebuilds only those units).
    ST="$CG/staging"
    rm -rf "$ST"
    mkdir -p "$ST"
    cp "$CG/gow2_manifest.toml" "$ST/"
    cp -R "$CG/hints" "$ST/hints"
    ln -s ../game "$ST/game"
    echo "== codegen"
    (cd "$ST" && REX_DUMP_IMAGE="$CG/image.bin" "$REXGLUE" --force codegen gow2_manifest.toml > "$CG/codegen.log" 2>&1) || {
        tail -20 "$CG/codegen.log"; exit 1; }
    GEN="generated/default"
    # The PC port's fixes (gears-of-war-2-pc-port/tools, BSD-3-Clause):
    #   patch_switch_traps.py   jump tables the codegen under-counts and branches to targets it never found become
    #                           dispatches through the function table (or gotos within the function)
    #   patch_game_patches.py   xenia-canary's game patches for this executable, each behind Gow2GamePatch(id)
    #                           (ps4/gow2_ps4_game.cpp): id 1 GUseTilingMode = FALSE (no predicated tiling: the
    #                           scene drawn once instead of per EDRAM tile, the V8 port's v00.10 lesson), 2 texture
    #                           streaming pool, 3 16x anisotropy, 4 frame rate unlock, 5/6 AO and DoF fixes, 7 wide
    echo "== the PC port's fixes"
    (cd "$ST" && python3 -I "$PCTOOLS/patch_switch_traps.py" "$GEN/*.cpp") > "$CG/patch_switch_traps.log" 2>&1 || {
        tail -20 "$CG/patch_switch_traps.log"; exit 1; }
    tail -3 "$CG/patch_switch_traps.log"
    (cd "$ST" && python3 -I "$PCTOOLS/patch_game_patches.py" "$GEN/*.cpp") > "$CG/patch_game_patches.log" 2>&1 || {
        tail -20 "$CG/patch_game_patches.log"; exit 1; }
    tail -1 "$CG/patch_game_patches.log"
    # Then the V8 port's PS4 passes (MP3-PS4's, from gears2-nx and dantes-inferno-nx, GPL-3.0), in its order:
    #   patch_vmx_exact.py     vmaddfp/vnmsubfp as REX_VMADDFP/REX_VNMSUBFP (unfused on the Jaguar by the PS4 PCH)
    #   ps4_unfused_fma.py     the fmadd family as REX_FMA: the Jaguar has no FMA unit, std::fma would be libm's
    #   patch_stack_access.py  guest stack accesses without volatile (REX_SLOAD/REX_SSTORE in the PCH)
    #   patch_inline_calls.py  same-file calls to functions no hook replaces call the body; the register save/restore
    #                          helpers (__savegprlr_N ...) become always-inline copies (gow2_inline_helpers.h)
    #   patch_local_regs.py    every guest register in a host local, ctx exact only at calls and returns, for the
    #                          registers a callee or caller can see (LOCALREGS=0 skips it)
    #   patch_phys_base.py     register + displacement accesses take the 0xE0000000 heap's offset from their base
    #                          register, not from every address
    # The functions the PS4 sources name (REX_EXTERN hooks) keep their calls through the alias.
    echo "== the PS4 passes"
    (cd "$ST" && python3 -I "$TOOLS/patch_vmx_exact.py" $GEN/gow2_recomp.*.cpp) > "$CG/patch_vmx_exact.log"
    tail -1 "$CG/patch_vmx_exact.log"
    (cd "$ST" && python3 -I "$TOOLS/ps4_unfused_fma.py" $GEN/gow2_recomp.*.cpp) > "$CG/ps4_unfused_fma.log"
    tail -1 "$CG/ps4_unfused_fma.log"
    (cd "$ST" && python3 -I "$TOOLS/patch_stack_access.py" $GEN/*.cpp) > "$CG/patch_stack_access.log"
    tail -1 "$CG/patch_stack_access.log"
    HOOK_DIRS="$SRC/ps4 $SDK/src $SDK/include"
    (cd "$ST" && python3 -I "$TOOLS/patch_inline_calls.py" $HOOK_DIRS -- $GEN/gow2_recomp.*.cpp) \
        > "$CG/patch_inline_calls.log"
    tail -1 "$CG/patch_inline_calls.log" | cut -c1-200
    if [ "${LOCALREGS:-1}" = 1 ]; then
        (cd "$ST" && python3 -I "$TOOLS/patch_local_regs.py" $GEN/gow2_inline_helpers.h $HOOK_DIRS \
            -- $GEN/gow2_recomp.*.cpp) > "$CG/patch_local_regs.log" 2>&1 || { tail -20 "$CG/patch_local_regs.log"; exit 1; }
        tail -1 "$CG/patch_local_regs.log"
    fi
    (cd "$ST" && python3 -I "$TOOLS/patch_phys_base.py" $GEN/gow2_recomp.*.cpp) > "$CG/patch_phys_base.log"
    tail -1 "$CG/patch_phys_base.log"
    # Anything the fixes left: a trap here is a crash at run time.
    left=$( (grep -l -E 'REX_FATAL\("Unresolved|__builtin_trap\(\); // Switch case out of range' "$ST"/$GEN/*.cpp 2>/dev/null || true) | wc -l)
    echo "unresolved branch traps left in $left files"
    python3 -I - "$ST/$GEN" "$CG/$GEN" <<'PY'
import filecmp, os, shutil, sys
new, old = sys.argv[1:]
os.makedirs(old, exist_ok=True)
names = set(os.listdir(new))
changed = 0
for n in sorted(names):
    a, b = os.path.join(new, n), os.path.join(old, n)
    if not os.path.isfile(b) or not filecmp.cmp(a, b, shallow=False):
        shutil.copy2(a, b)
        changed += 1
for n in set(os.listdir(old)) - names:
    os.remove(os.path.join(old, n))
print(f"generated/default: {changed} of {len(names)} files changed")
PY
    rm -rf "$ST"
    grep -E "Codegen summary|functions|error" "$CG/codegen.log" | tail -5 || true
    echo "codegen: $(ls "$CG"/generated/default/*.cpp | wc -l) files in $CG/generated/default, image $CG/image.bin"
    ;;
app)
    [ -f "$CG/generated/default/sources.cmake" ] || { echo "run '$0 codegen' first" >&2; exit 1; }
    B="${GOW2_APP_BUILD:-$V/build-app}"
    echo "== configure"
    ps4_cmake -S "$SRC/ps4" -B "$B" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_PROJECT_gow2_INCLUDE="$PS4_KIT/ps4-kit.cmake" -DPS4_KIT_NETFS=OFF \
        -DREXSDK_DIR="$SDK" -DGOW2_CODEGEN_DIR="$CG" -DREXGLUE_PLATFORM_PS4=ON -DREXGLUE_BUILD_HOST_TOOLS=OFF \
        -DREXGLUE_USE_VULKAN=ON -DREXGLUE_ENABLE_TRACY=OFF -DREXGLUE_BUILD_TESTS=OFF \
        -DGOW2_VERSION="${GOW2_VERSION:-00.00}" \
        > "$V/logs/configure-app.log" 2>&1 || { tail -40 "$V/logs/configure-app.log"; exit 1; }
    # Each generated unit takes ~1.5 GB of RAM to compile (the MGR port's measure).
    mem_mb=$(( $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) / 1024 ))
    JOBS=$(( mem_mb / 1500 )); [ "$JOBS" -lt 1 ] && JOBS=1; [ "$JOBS" -gt "$(nproc)" ] && JOBS=$(nproc)
    echo "== build (${GOW2_TARGETS:-gow2_eboot}, -j$JOBS)"
    ninja -C "$B" -k 0 -j"$JOBS" ${GOW2_TARGETS:-gow2_eboot} > "$V/logs/build-app.log" 2>&1 \
        || { grep -E "error:|FAILED|undefined symbol|missing module" "$V/logs/build-app.log" | head -80; exit 1; }
    echo "app built"
    ;;
pkg)
    # out/GOW2-vXX.YY.pkg: the eboot, and with GOW2_PKG_GAME=1 your extracted disc as game/ (read from /app0/game).
    # Without it the app reads the game from /data/GOW2/game (scripts/upload-game.py puts it there once). A package
    # with the game inside holds your game: it goes to your own console and nowhere else.
    VERSION="${GOW2_VERSION:-00.00}"
    B="${GOW2_APP_BUILD:-$V/build-app}"
    EBOOT="$B/gow2_eboot/eboot.bin"
    [ -f "$EBOOT" ] || { echo "no $EBOOT: run '$0 app' first" >&2; exit 1; }
    STAGE="$V/stage"
    rm -rf "$STAGE"
    mkdir -p "$STAGE/sce_sys"
    cp "$EBOOT" "$STAGE/eboot.bin"
    # sce_sys/local/ (your own pictures, game art: kept out of the repository) before sce_sys/ (original art).
    for f in icon0.png pic1.png; do
        if [ -f "$HERE/sce_sys/local/$f" ]; then
            cp "$HERE/sce_sys/local/$f" "$STAGE/sce_sys/"
        elif [ -f "$HERE/sce_sys/$f" ]; then
            cp "$HERE/sce_sys/$f" "$STAGE/sce_sys/"
        fi
    done
    [ -f "$STAGE/sce_sys/icon0.png" ] || { echo "no sce_sys/icon0.png in $HERE" >&2; exit 1; }
    if [ "${GOW2_PKG_GAME:-0}" = 1 ]; then
        [ -f "$GAME/default.xex" ] || { echo "no $GAME/default.xex" >&2; exit 1; }
        mkdir -p "$STAGE/game"
        for entry in "$GAME"/*; do
            # The disc's Xbox 360 system update is never read (scripts/upload-game.py leaves it out too).
            case "$(basename "$entry")" in System_Update.pad|'$SystemUpdate') continue ;; esac
            cp -al "$entry" "$STAGE/game/" 2>/dev/null || cp -a "$entry" "$STAGE/game/"
        done
        echo "in the package: $(cd "$STAGE" && du -sh game | tr '\t\n' '  ')"
    fi
    PKG="$(bash "$PS4_KIT/scripts/make-pkg.sh" "$STAGE" GEAR00002 "Gears of War 2" "$VERSION" GOW2 "$PSB/out" | tail -1)"
    mkdir -p "$HERE/out" "$V/oelf"
    SUFFIX=""; [ "${GOW2_PKG_GAME:-0}" = 1 ] && SUFFIX="-full"
    cp "$PKG" "$HERE/out/GOW2-v$VERSION$SUFFIX.pkg"
    cp "$B/gow2" "$V/oelf/v$VERSION.elf" 2>/dev/null || true
    ls -la "$HERE/out/GOW2-v$VERSION$SUFFIX.pkg"
    ;;
*)
    echo "usage: $0 host|codegen|app|pkg" >&2
    exit 2
    ;;
esac
