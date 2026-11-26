# Credits and licences

This repository holds build scripts and patches:

- `patches/gow2-ps4.patch`, against [santiquiroz/gears-of-war-2-pc-port](https://github.com/santiquiroz/gears-of-war-2-pc-port)
  at the commit in `patches/BASE.txt`: the PS4 app (`ps4/`), the PS4 code generation passes (`ps4/tools/`) and the
  hot-function link order (`ps4/order/hot-order.txt`)
- `patches/sdk-gow2.patch`, against the PS4 SDK of [Vigilante-8-Arcade-PS4](https://github.com/iHaiDeeZ/Vigilante-8-Arcade-PS4):
  [nx-mod/rexglue-sdk-nx](https://github.com/nx-mod/rexglue-sdk-nx) at the commit in `patches/BASE.txt`, with
  [iHaiDeeZ/MP3-PS4](https://github.com/iHaiDeeZ/MP3-PS4)'s `patches/sdk-ps4.patch` and Vigilante-8-Arcade-PS4's
  `patches/sdk-vig8.patch` (at the commits in `patches/BASE.txt`)
- `patches/host/`: two changes to the host build of the ReXGlue code generator (MP3-PS4's image dump, SDL without a
  display), as Vigilante-8-Arcade-PS4 carries them
- `patches/mesa/`: two of ps4-kit's Mesa patches that aren't in the published kit yet (the flight recorder's 32
  submissions; the tessellation factor ring)
- `patches/ffmpeg/`: the PS4 configuration of FFmpeg (from MGR-PS4)
- `patches/fonts/`: the quick menu's font

`scripts/clone-gow2.sh` fetches the sources and applies the patches. The patched files keep their own licences.

| Part | Where | Licence |
|---|---|---|
| [gears-of-war-2-pc-port](https://github.com/santiquiroz/gears-of-war-2-pc-port) (santiquiroz): the ReXGlue recompilation of Gears of War 2 for Windows and Linux - its code generator manifest, function hints and generated-code fixes (jump tables, unresolved branches, xenia-canary's game patches as switches) | the upstream repository; the patch adds `ps4/` | BSD-3-Clause (upstream `LICENSE`) |
| [gears2-nx](https://github.com/VasilkovND/gears2-nx) (VasilkovND): the Switch port, whose native versions of the game's busiest small functions `ps4/gow2_ps4_native.cpp` rewrites for the PS4 | `ps4/gow2_ps4_native.cpp`, added by the patch | GPL-3.0 |
| The code generation passes of [mp3-nx](https://github.com/VasilkovND/mp3-nx) (VasilkovND), from gears2-nx and dantes-inferno-nx, with MP3-PS4's and Vigilante-8-Arcade-PS4's PS4 passes | `ps4/tools/`, added by the patch | GPL-3.0 (mp3-nx's `LICENSE`) |
| [xenia-canary](https://github.com/xenia-canary/xenia-canary)'s game patches for Gears of War 2 (Black Shading Fix, Texture Streaming Fix, 16x Anisotropic Filtering, Unlock FPS, AO and DoF Upscaling Fixes) | the PC port's `tools/patch_game_patches.py`; switched by `ps4/gow2_ps4_game.cpp` | as the PC port and xenia-canary's game-patches repository give them |
| [rexglue-sdk-nx](https://github.com/nx-mod/rexglue-sdk-nx) (nx-mod) on the [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk) v0.10.0 (Tom Clay), with portions from [Xenia](https://xenia.jp) (Ben Vanik and the Xenia contributors) | the SDK; MP3-PS4's patch adds the PS4 platform layer, Vigilante-8-Arcade-PS4's its command processor work, this port's patch the changes for this game | BSD-3-Clause (the SDK's `LICENSE`) |
| [libmspack](https://www.cabextract.org.uk/libmspack/) (Stuart Caie): the LZX decoder the native `XMemDecompress` uses | the SDK's `thirdparty` | LGPL-2.1 |
| [FFmpeg](https://ffmpeg.org) (the XMA decoder) | the SDK's `thirdparty/FFmpeg`, from rexglue-sdk's submodule; `patches/ffmpeg/` is the PS4 configuration | LGPL-2.1-or-later (configured without GPL parts) |
| The SDK's other libraries (fmt, spdlog, toml++, Dear ImGui, xxHash, SIMDe, glslang, SPIRV-Tools, Vulkan Memory Allocator and the rest) | the SDK's `thirdparty`, from rexglue-sdk v0.10.0 (`c94f5eb`) and its submodules | their own licences, listed in rexglue-sdk's `THIRD_PARTY_NOTICES.md` |
| [Lato](https://www.latofonts.com) (Łukasz Dziedzic) | `patches/fonts/`, copied into `ps4/fonts/`: the quick menu's type; also the title of the README's banner | SIL Open Font License 1.1 (`patches/fonts/LICENSE-Lato.txt`) |
| [ps4-kit](https://github.com/iHaiDeeZ/ps4-kit) (iHaiDeeZ): toolchain setup, runtime, Mesa RADV for the PS4, VideoOut swapchain, crash log, profiler, packaging | linked at build time; `patches/mesa/` holds two of its Mesa patches | MIT |
| [Mesa](https://mesa3d.org) RADV | built by ps4-kit | MIT |
| [OpenOrbis](https://github.com/OpenOrbis) toolchain ([PacBrew](https://github.com/PacBrew)) | build host | GPL-3.0 (tools), the C library under its own licences |

This port's own code in the patches is under the licence of the folder it is in: GPL-3.0 in `ps4/` and `ps4/tools/`
(the passes and the native functions it carries are GPL-3.0), BSD-3-Clause in the SDK. The build scripts, the tools
(`tools/`: the decompilation and profile readers) and the rest of this repository are GPL-3.0 (`LICENSE`).
`scripts/host-deps.sh` and `patches/host/` come from Vigilante-8-Arcade-PS4, `scripts/upload-game.py` from MP3-PS4.

The game itself (code, art, sound, text) belongs to its owners. Nothing from it is in this repository: the build reads
your `default.xex` and the game's files on your own machine, and the decompilation tools write their tables from your
copy too (they're not in the repository). The package's icon and background are drawn by `scripts/make-icon.py`
unless you put your own pictures in `sce_sys/local/`. The banner of this README is original art drawn by
`scripts/make-banner.py`: a plain gear wheel, not the game's emblems.
