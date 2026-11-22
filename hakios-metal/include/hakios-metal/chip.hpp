// The Adreno this driver is talking to: the numbers in a6xx.hpp's tables that are the chip's own, and the row each
// chip id resolves to in Mesa's src/freedreno/common/freedreno_devices.py (Mesa 25.0.7).
//
// Everything else in a6xx.hpp is the same on every chip this driver serves -- the registers, the packets, the
// descriptor fields -- and so are most of these: what actually differs between the two Adrenos here is how many CCUs
// and SP cores there are (the local buffer's split, the CCU's colour cache), the tile grid's width alignment, the
// on-chip memory's size and its highest bank bit. The rest of the struct is filled in because a row of Mesa's table
// has it, and a chip added later will want it.
//
//   0x06030500  Adreno 7c+ Gen 3   a6xx_base + a6xx_gen4   num_ccu 2   tile_align_w 32   512 KiB   bank bit 14
//   0x06060010  Adreno 642         GPUId(660), gen4        num_ccu 3   tile_align_w 96   1.5 MiB   bank bit 16
//
// The second one is the Mi 11 Lite 5G's, whose device tree says highest bank bit 15 where Mesa's row says 16: the
// kernel programs the hardware from the device tree (drivers/gpu/hakios.adreno.c's step 20), so where the kernel
// answers GET_PARAM GMEM_SIZE and HIGHEST_BANK_BIT its answer is what this driver uses -- the layout userspace asks
// the GPU for has to agree with the registers the kernel wrote.
#pragma once

#include <cstdint>

namespace hakios::metal {

struct Chip {
    uint32_t chipId = 0;          // dt qcom,chipid, without the speed bin above it
    const char* name = "";        // the row's name in Mesa's table

    // the shader compiler and the emitters: Mesa's instr_cache_size, fibers_per_sp, threadsize_base
    uint32_t instrCacheSize = 0, fibersPerSp = 0, threadsizeBase = 0;

    // the tile grid: Mesa's tile_align_w/h, tile_max_w/h and gmem_align_w/h
    uint32_t tileAlignW = 0, tileAlignH = 0, tileMaxW = 0, tileMaxH = 0, gmemAlignW = 0, gmemAlignH = 0;

    // the cores, and the on-chip memory's shape
    uint32_t numCcu = 0, numSpCores = 0, numVscPipes = 0;
    uint32_t csSharedMemSize = 0, waveGranularity = 0, maxWaves = 0;
    uint32_t sysmemPerCcuColorCacheSize = 0, sysmemPerCcuDepthCacheSize = 0;
    uint32_t gmemCcuColorCacheFraction = 0;   // fd6_emit_ccu_cntl's CCU_CNTL divisor: QUARTER is 4

    // the layouts of the GPU's own tiled and compressed images: Mesa's ubwc_swizzle and macrotile_mode
    uint32_t ubwcSwizzle = 0, macrotileMode = 0;

    // PC_POWER_CNTL, which the batch start writes: Mesa's magic_regs, and the one of them that differs between the two
    // rows (a6xx.hpp's kMagic* are the rest, and are the same on both)
    uint32_t pcPowerCntl = 0;

    // the core's own memory and the bank bit: the row's, unless the kernel answered (chipSetFromKernel)
    uint32_t gmemBytes = 0, highestBankBit = 0;

    // The GMEM below the CCU's colour cache: what a render pass may tile into (fd6_emit_ccu_cntl's
    // ccu_offset_gmem = gmem - num_ccu * color cache / fraction).
    uint32_t gmemCcuColorOffset() const {
        return gmemBytes - numCcu * sysmemPerCcuColorCacheSize / gmemCcuColorCacheFraction;
    }
};

// Mesa's rows, as freedreno_devices.py writes them (the `not-in-headers:` values a6xx.hpp documents one of).
constexpr Chip chipA635() {
    Chip c;
    c.chipId = 0x06030500;
    c.name = "Adreno 7c+ Gen 3";
    c.instrCacheSize = 127;                  // a6xx_gen4: "Blob limits it to 128 but we hang with 128"
    c.fibersPerSp = 128 * 2 * 16;
    c.threadsizeBase = 64;
    c.tileAlignW = 32; c.tileAlignH = 16;
    c.tileMaxW = 1024; c.tileMaxH = 1008;
    c.gmemAlignW = 16; c.gmemAlignH = 4;
    c.numCcu = 2; c.numSpCores = 2; c.numVscPipes = 32;
    c.csSharedMemSize = 32 * 1024; c.waveGranularity = 2; c.maxWaves = 16;
    c.sysmemPerCcuColorCacheSize = 64 * 1024; c.sysmemPerCcuDepthCacheSize = 64 * 1024;
    c.gmemCcuColorCacheFraction = 4;         // CCUColorCacheFraction.QUARTER
    c.ubwcSwizzle = 6; c.macrotileMode = 1;
    c.pcPowerCntl = 1;                       // Mesa's magic_regs PC_POWER_CNTL
    c.gmemBytes = 512 * 1024;                // the A635's, as the reference phone's kernel answers
    c.highestBankBit = 14;
    return c;
}

constexpr Chip chipA660() {
    Chip c;
    c.chipId = 0x06060010;
    c.name = "Adreno 642";                   // Mesa's GPUId(660), matched on chipid >> 8 (its low byte is 0xff)
    c.instrCacheSize = 127;
    c.fibersPerSp = 128 * 2 * 16;
    c.threadsizeBase = 64;
    c.tileAlignW = 96; c.tileAlignH = 16;    // three CCUs of 32
    c.tileMaxW = 1024; c.tileMaxH = 1008;
    c.gmemAlignW = 16; c.gmemAlignH = 4;
    c.numCcu = 3; c.numSpCores = 3; c.numVscPipes = 32;
    c.csSharedMemSize = 32 * 1024; c.waveGranularity = 2; c.maxWaves = 16;
    c.sysmemPerCcuColorCacheSize = 64 * 1024; c.sysmemPerCcuDepthCacheSize = 64 * 1024;
    c.gmemCcuColorCacheFraction = 4;
    c.ubwcSwizzle = 6; c.macrotileMode = 1;
    c.pcPowerCntl = 2;                       // Mesa's magic_regs PC_POWER_CNTL for GPUId(660)
    c.gmemBytes = 1024 * 1024 + 512 * 1024;  // the vendor's a642 core: SZ_1M + SZ_512K
    c.highestBankBit = 16;                   // the row's; the phone's kernel answers 15 and wins
    return c;
}

inline constexpr Chip kChipA635 = chipA635();
inline constexpr Chip kChipA660 = chipA660();

// The row a chip id resolves to (Mesa matches on the upper 24 bits for the rows whose low byte is 0xff), or nullptr.
const Chip* chipFor(uint32_t chipId);

// Choose the chip the process is talking to, from the chip id the kernel gave (a chip no row is returns false and
// leaves the row that is there: the caller refuses the GPU, the tables would be another's). The driver opens one GPU
// once, at start; the tests move between rows with this.
bool chipSelect(uint32_t chipId);

// What the kernel says of the chip it is driving (GET_PARAM GMEM_SIZE and HIGHEST_BANK_BIT), 0 for "it did not say".
// The kernel programs the hardware from the phone's device tree, so this wins over the row.
void chipSetFromKernel(uint32_t gmemBytes, uint32_t highestBankBit);

// The chip chosen above: the reference phone's until one is chosen, so that a build with no GPU (and the tests) keeps
// the tables it had.
const Chip& chip();

}  // namespace hakios::metal
