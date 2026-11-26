# Development notes

How this port is put together, what it changes, and what was found on the way. The build steps for players are in
the [README](../README.md).

## The game

| | |
|---|---|
| Release | Xbox 360 retail disc, title `4D53082D`, `default.xex` version 0.0.0.5 (no title update), SHA-1 `b6860bf31e55013467b53eca963d12314c0d78da`: the executable the PC port was recompiled from |
| Files | 6.3 GB in 1,810 files once unpacked: `default.xex`, `GearGame/` (`CookedXenon` packages, `Textures.tfc`, movies), the `.pad` files; the disc's `System_Update.pad` is never read and stays out of the package |
| Code | 0x82220000-0x82F5D8AC: about 13 MB of PowerPC, 48,830 functions after the code generator (Unreal Engine 3 and the XDK libraries; the D3D runtime around 0x8297-0x8298) |

## The route

| Part | PS4 |
|---|---|
| Code generator | ReXGlue **v0.10.0**, built for the host by `scripts/build-gow2.sh host` (rexglue-sdk at `c94f5eb` with `patches/host/`: an image dump for disassembly, SDL without a display; X11/Wayland development files unpacked by `scripts/host-deps.sh`, no root needed). The PC port's manifest and function hints, its `*_as_local` options taken out (the PS4 pass does the same with a whole-program analysis): 454 generated files, no traps left |
| The PC port's fixes (`tools/`, BSD-3-Clause) | `patch_switch_traps.py` (jump tables and unresolved branches), `patch_game_patches.py`: xenia-canary's patches as `Gow2GamePatch(id)` switches the PS4 app answers (1 Black Shading Fix = no predicated tiling, 2 Texture Streaming Fix, 3 16x anisotropy, 4 Unlock FPS, 5 AO fix, 6 DoF fix, 7 widescreen off, 8-9 heights 720) |
| PS4 passes (`ps4/tools`, from mp3-nx, MP3-PS4 and Vigilante-8-Arcade-PS4, GPL-3.0) | `patch_branch_traps.py`, `patch_vmx_exact.py`, `ps4_unfused_fma.py` (every `std::fma` as a multiply and an add: the Jaguar has no FMA unit), `patch_stack_access.py`, `patch_inline_calls.py` (same-file calls and helpers inlined; calls to functions the PS4 sources hook with `REX_EXTERN` are kept), `patch_local_regs.py` (guest registers in host locals), `patch_phys_base.py`, `make_ps4_pch.py` |
| Generated code | `-O2 -march=btver2 -g0 -ffp-contract=off -fno-strict-aliasing -ffunction-sections`; the eboot's text is about 50 MB, and `ps4/order/hot-order.txt` (`tools/make_order.py` from a profile of a busy fight) puts the ~6,400 sampled functions (about 8 MB) first through ld.lld's `--symbol-ordering-file` |
| Runtime | the SDK of Vigilante-8-Arcade-PS4 (rexglue-sdk-nx + MP3-PS4's PS4 layer + Vigilante 8's command processor work) and `patches/sdk-gow2.patch` |
| The app (`ps4/`) | `main_ps4.cpp` (the game folder: `/app0/game`, else `/data/GOW2/game`), `gow2_ps4.cpp` (settings, the engine options, v-sync, diagnostics), `gow2_ps4_game.cpp` (the game patch switches, the depth pre-pass hooks), `gow2_ps4_native.cpp` (native functions), `gow2_ps4_menu.cpp` (the quick menu), `gow2_ps4_achievements.cpp` |

## Changes to the SDK (`patches/sdk-gow2.patch`)

- **Pipelines that don't stop the game** (`vulkan/pipeline_cache.cpp`, `command_processor.cpp`): with
  `vulkan_pipeline_skip_pending` a draw whose pipeline is still being created is left out until it exists, instead
  of the async path's placeholder compiled on the command thread; `EndSubmission` no longer compiles the queue and
  waits; the creation threads run at priority 767 (below the game's); a frame with more than
  `vulkan_pipeline_hold_share` % of its draws left out keeps the previous picture (at most 30 frames in a row). The
  app turns on RADV's disk cache (`MESA_SHADER_CACHE_DIR=/data/GOW2/cache/mesa`): the SDK's stored pipelines come back
  at start from it in a moment.
- **`vblank_from_display`** (`graphics_system.cpp`, PS4): a "Display VBlank" thread waits on ps4-kit's
  `wait_vblank` and each display vblank fires one guest vblank, instead of a 60.00 Hz clock next to the TV's
  59.94 Hz; back on the clock if no vblank comes for 0.5 s. With flips at the vblank (the app's `gow2_vsync`, ps4-kit's
  `set_force_vsync`), a 30 fps frame shows for exactly two refreshes.
- **The repeat-draw shortcut** (`vulkan_repeat_draw_shortcut`, live): `state_changes_since_draw_` counts every
  register value change except the shader constants, the draw's own VGT registers, scratch and coherency (the bulk
  register paths only take constant ranges past it). A draw with no such change since the last drawn one, with the
  same shaders and primitive type, takes that draw's shader modifications and translations, pipeline (when the render
  pass, colour mask and the primitive result's fields the pipeline reads are the same) and viewport; with no fetch
  constant written, in the same submission, and with the texture cache's new `bindings_generation()` unchanged
  (bumped by binding changes, loads, resets, outdated textures and destructions), its samplers and texture
  descriptor sets too (`UpdateBindings` keeps the sets' up-to-date bits). The cache is set only by a draw that
  reaches its draw command, never with memory export or a placeholder pipeline. `vulkan_repeat_draw_verify` (200,000):
  the first repeat draws of a session and 1 in 64 after that do the full work and compare; any difference logs
  `[repeat] ... differ` and turns the shortcut off for the session. `[cp2]` counts the shortcut's draws.
- **Diagnostics**: `rex_gpu_last_frame_draws` (the app's automatic profile only counts seconds of busy gameplay),
  `[pipe]` lines (draws left out, frames held, the creation queue), `gpu_vertex_buffer_state_skip` (off: vertex
  buffers requested again in every frame).
- `shared_memory.cpp`: the compute-write barrier's access mask includes reads.

## Decompilation (`tools/`)

The tools read the code generator's image dump (`REX_DUMP_IMAGE`, written by `codegen` to
`~/gow2-build/codegen/image.bin`) and the generated register file; what they write stays on your machine.

- `ue3_natives.py`: Unreal's native function tables (UTF-16 `int<Class>exec<Func>` names next to their addresses);
  `ue3_classes.py`: class registration (`GetPrivateStaticClass`, the name one character in); `ue3_vtables.py`: vtables
  bounded by every vtable-like address the code loads; `make_symbols.py` merges them with hand-named functions into
  one table (about 12,000 names). `annotate.py` names a profile, crash log or freeze report with it.
- `xrefs.py` (who builds an address, who calls a function, a function's constants), `field_readers.py` (who loads or
  stores a global's field), `disasm.py` (capstone), `settings_table.py` (FSystemSettings' loader table).
- Found that way: Unreal's depth pre-pass (`TDepthOnlyVertexShader` -> its shader types -> the drawing policy
  constructors -> `FDepthDrawingPolicyFactory::AddStaticMesh` `sub_826FD078` and `DrawDynamicMesh` `sub_826FD1F0`,
  hooked by the app); `GSystemSettings` at `0x8313751C` with 57 keys from its loader `sub_82350278`. Its fields start
  **4 bytes in**: `+0` is a vtable pointer (only the two constructors store there), and the loader's offsets are from
  the data. Proof by readers: `0x83137548` (data + 0x28, MotionBlur) is read only by `UMotionBlurEffect` and
  `UUberPostProcessEffect`; `0x83137544` (DirectionalLightmaps) by 16 functions in mesh drawing.
- The D3D runtime's shader constant setters (`sub_82982BA0` vertex, `sub_82982C80` pixel): `count` float4s from an
  unaligned source to `dev + 1920 / 6016 + 16 x first` (16-byte aligned stores, four at a time, then one by one), then
  the 64-bit big-endian OR of the dirty bits at `dev + 0 / 8`. Native since v00.05, in the same order.

## History

- **v00.01**: plays, the picture right. About 150 freezes of 100-800 ms in the first minutes, measured frame by frame
  in a capture: Vulkan pipelines compiled on the command thread (~20 ms each on the Jaguar) and RADV's disk cache off.
  Heavy fights 18-26 fps.
- **v00.02**: the pipeline changes above: no more hitches. Heavy fights 17-23 fps at 2,300-3,200 draws, the render
  thread the limit; a GPU census found 533 of 1,936 draws to be Unreal's depth pre-pass.
- **v00.03**: the depth pre-pass left out (`gow2_depth_prepass`, the same picture), the frame rate unlocked by
  default, the engine settings in the quick menu. Busy places 24-37 fps at 1,070-1,500 draws, quiet ones 42-48.
- **v00.04**: native memcpy, memset, Unreal's TMap find by name, bone matrices and `XMemDecompress` (libmspack LZX),
  from gears2-nx, with the recompiled code taking any unusual argument. 29-51 fps in the same places.
- **v00.05**: a capture of "blur" in movement showed **tearing** (a frame's top and bottom from two moments): v-sync
  and the display-locked vblank. The game's own motion blur also smears the picture in a roadie run. Native shader
  constant setters, the hot-function order, the automatic profile only in busy gameplay. Two bottlenecks showed by
  scene: 4,000+ draw views limited by the command processor (~11 us a draw, 95 % of its core), fights by the render
  thread.
- **v00.06**: the engine options written 4 bytes low until then (see above: "Motion blur off" had switched off the
  lightmaps, black surfaces), now at the data's offsets; motion blur off by default. Busy places 22-39 fps at
  600-2,400 draws (World detail Medium now really drops objects); the game thread became the limit in fights, its
  profile flat (the biggest function 2.3 %, animation about 10 % together).
- **v00.07**: the repeat-draw shortcut with its check; the package can carry the game (`GOW2_PKG_GAME=1`).

## Reading a session

The log (`/data/GOW2/logs/gow2_NNN.log`) has a block every 10 s:

- `[frames]`: frames a second; `[cp]`: swaps, draws, resolves and submissions a frame; `[cpt]`/`[cpt2]`/`[cpt3]`: the
  command processor's time by part; `[cp2]`: same-state draws and the repeat-draw shortcut; `[wait]`: its waits and
  its share of its core; `[cores]`: every core's load; `[pipe]`: draws left out for their pipelines; `[memory]`: free
  system memory and the game's objects; `[settings]`: an engine option written.
- `tools/perf_timeline.py <log> --summary`: the windows as one table, and frame rates by draws a frame.
- A profile (`profiles/profile_N.txt`): ps4-kit's `scripts/profile.py --elf <the eboot's ELF>` names it;
  `tools/self_time.py <profile> <ELF> <thread>` adds up every sample by function (the named file lists only its
  biggest stacks); `tools/annotate.py` adds the decompilation's names. The ELF of each build is kept in
  `~/gow2-build/oelf/`.
- A capture of the screen: `tools/clip_hitches.py` measures runs of repeated frames.
