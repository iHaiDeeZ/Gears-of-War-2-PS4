#!/usr/bin/env python3
"""Gears of War 2 (retail 0.0.0.5): one symbol table from the decompilation's sources.

  natives.tsv   tools/ue3_natives.py: UE3's native function lookup tables (Class::execFunction)
  classes.tsv   tools/ue3_classes.py: UE3's class registration (GetPrivateStaticClass, InternalConstructor)
  KNOWN below   functions the PC port (gears-of-war-2-pc-port) and gears2-nx identified and hook, and the functions
                that hold xenia-canary's game patch sites

  vtables_functions.tsv  tools/ue3_vtables.py (optional 4th argument): virtual functions named after the class with
                the fewest slots holding them at that slot, as <Class>::vf<slot> (the slot's method name is not in the
                image); only for addresses nothing above names

usage: make_symbols.py <natives.tsv> <classes.tsv> <out symbols.tsv> [vtables_functions.tsv]
Output: address, name, source; one name per address (a native shared by several classes through identical-code
folding keeps the first, the others listed in a fourth column).
"""
import sys
from collections import defaultdict

KNOWN = {
    # The PC port's hooks (src/*.cpp, REX_HOOK_RAW) and comments.
    0x824A2EA0: "UGameEngine::Tick",                 # gow2_engine_tick_hook.cpp: r3 engine, f1 delta, once a frame
    0x828A4180: "UGearEngine::Tick",                 # calls UGameEngine::Tick
    0x8283F780: "FStartupPackages::LoadAll",         # gow2_script_patch_hook.cpp (called once, from 0x8284075C)
    0x82AA85B8: "Sleep",                             # gow2_idle_worker.cpp: guest Sleep(ms), 0 = yield
    0x82977688: "D3D::GpuWaitPoll",                  # gow2_gpu_wait.cpp: the D3D runtime's wait for GPU progress
    0x8298F378: "D3D::LoadAluConstantPacket",        # gow2_native_frontend.cpp: the LOAD_ALU_CONSTANT emitter
    0x8298E5B8: "D3D::FlushAluConstantShadow",       # the ALU constant shadow flush
    0x82981ED8: "D3DDevice_Clear",                   # every draw Clear emitted is processed when it returns
    0x8298C1A0: "D3D::KickSegment",                  # ring space check and segment kick-off
    0x8298C2A0: "D3D::WaitForRingSpace",             # gow2_gpu_wait.cpp: waits for ring buffer space (return 0x8298C360)
    0x8298D430: "D3DDevice_Swap",                    # gow2_gpu_wait.cpp: D3D Swap (its GPU wait returns to 0x8298DB80)
    0x82980B20: "D3DDevice_DrawIndexedVertices",     # gow2_native_frontend.cpp: DrawIndexed, writes DRAW_INDX at dev+48
    0x82980210: "D3D::DrawWithStateRestore",         # a draw that restores state and bin masks; 0 on success
    0x8297FD30: "D3DDevice_BeginVertices",           # returns the vertex pointer (0 and dev+48 on failure)
    0x829813F0: "D3D::ClearRectList",                # Clear's rectangle-list draw
    0x8298F600: "D3D::FlushShaders",                 # IM_LOAD of the bound vertex/pixel shaders
    0x8298F210: "D3D::LoadShaderImmediate",          # IM_LOAD_IMMEDIATE
    0x828294A0: "OnlineSubsystem::BuildLanResponse", # gow2 coop notes: the LAN response builder
    # gears2-nx's gow2/codegen/names.toml.
    0x829832E8: "D3DDevice_CreateVertexShader",      # instruction for instruction Dead Space 2's
    0x82982F20: "D3DDevice_CreatePixelShader",
    0x827F7638: "appOutOfMemory",                    # UE3's, called by the pooled allocator with the size it missed
    0x82AAA880: "VirtualAlloc",                      # the NtAllocateVirtualMemory wrapper (0 on failure)
    # The functions holding xenia-canary's game patch sites (the PC port's tools/patch_game_patches.py).
    0x828069F8: "RHI::InitTilingMode",               # patch 1 site 0x82806A44: the GUseTilingMode store
    0x82806A80: "RHI::SetupBackBuffer",              # patches 5/7/8: builds the back buffer from the display mode
    0x8280D4C8: "RHI::InitTexturePool",              # patch 2 site 0x8280D534: the pool size
    0x8280DDC8: "RHIGetTextureMemoryStats",          # patch 2: returns 0 when on
    0x8280E740: "RHI::InitSamplerStates",            # patch 3 site 0x8280E7FC: the max anisotropy
    0x824A2E78: "UGameEngine::GetMaxTickRate",       # patch 4 site 0x824A2E94: the frame limiter's rate
    0x8298CEC0: "D3D::SetPresentInterval",           # patch 4 site 0x8298CFB0: present interval 2 -> 1
    0x8272B1F8: "FAmbientOcclusion::OccluderHelper", # patch 5: returns at once when on
    0x82729610: "FDepthOfField::SampleWeights",      # patch 6
    0x82634F00: "FViewMatrices::Perspective1",       # patch 7 FOV sites
    0x82634CA8: "FViewMatrices::Perspective2",
}


def main():
    natives_path, classes_path, out_path = sys.argv[1:4]  # sys.argv[4]: vtables_functions.tsv (optional)
    names = {}
    others = defaultdict(list)
    for line in open(natives_path):
        if line.startswith("#"):
            continue
        addr, cls, fn, table = line.rstrip("\n").split("\t")
        a = int(addr, 16)
        n = f"{cls}::{fn}"
        if a in names:
            others[a].append(n)
        else:
            names[a] = (n, "native table")
    for line in open(classes_path):
        if line.startswith("#"):
            continue
        cls, gpsc, internal, static, init = line.rstrip("\n").split("\t")[:5]
        names.setdefault(int(gpsc, 16), (f"{cls}::GetPrivateStaticClass{cls}", "class registration"))
        names.setdefault(int(internal, 16), (f"{cls}::InternalConstructor", "class registration"))
    # The UObject defaults the linker folded (StaticConstructor/StaticInitializer of most classes).
    for line in open(classes_path):
        if line.startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t")
        for a in (int(cols[3], 16), int(cols[4], 16)):
            names.setdefault(a, ("UObject::StaticConstructor (empty, shared)", "class registration"))
    for a, n in KNOWN.items():
        names[a] = (n, "hook/patch site")
    if len(sys.argv) > 4:
        for line in open(sys.argv[4]):
            if line.startswith("#"):
                continue
            addr, n = line.rstrip("\n").split("\t")[:2]
            names.setdefault(int(addr, 16), (n, "vtable slot"))
    with open(out_path, "w") as out:
        out.write("# Gears of War 2 retail 0.0.0.5 (4D53082D, 63AF211E): guest address, name, source, other names\n")
        for a in sorted(names):
            n, src = names[a]
            out.write(f"0x{a:08X}\t{n}\t{src}\t{', '.join(others.get(a, []))}\n")
    by_src = defaultdict(int)
    for n, src in names.values():
        by_src[src] += 1
    print(f"{len(names)} functions named: " + ", ".join(f"{v} from {k}" for k, v in sorted(by_src.items())))


if __name__ == "__main__":
    main()
