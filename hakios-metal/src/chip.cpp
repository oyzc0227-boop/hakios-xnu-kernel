// The chip the process is talking to: the rows of Mesa's table (chip.hpp), and which of them the GPU the kernel gave
// this process is. One GPU per process, and the first to open it decides; before that the reference phone's row, which
// is what the driver's tables were written for.
#include "hakios-metal/chip.hpp"

#include <mutex>

namespace hakios::metal {
namespace {

std::mutex& lock() {
    static std::mutex m;
    return m;
}

Chip& current() {
    static Chip c = kChipA635;
    return c;
}

}  // namespace

const Chip* chipFor(uint32_t chipId) {
    if (chipId == 0) return nullptr;
    const Chip* rows[] = {&kChipA635, &kChipA660};
    for (const Chip* row : rows) {
        // the low byte of a row's id is the patch version, which a phone's chip id has and a table row may leave as
        // 0xff (Mesa matches on the upper 24 bits then); both forms are accepted here
        if (row->chipId == chipId) return row;
        if ((chipId & 0xffffff00u) == (row->chipId & 0xffffff00u)) return row;
    }
    return nullptr;
}

bool chipSelect(uint32_t chipId) {
    std::lock_guard<std::mutex> g(lock());
    const Chip* row = chipFor(chipId);
    if (row == nullptr) return false;
    current() = *row;                        // (the driver opens one GPU once; the tests change rows)
    return true;
}

void chipSetFromKernel(uint32_t gmemBytes, uint32_t highestBankBit) {
    std::lock_guard<std::mutex> g(lock());
    if (gmemBytes != 0) current().gmemBytes = gmemBytes;
    if (highestBankBit != 0) current().highestBankBit = highestBankBit;
}

const Chip& chip() {
    std::lock_guard<std::mutex> g(lock());
    return current();
}

}  // namespace hakios::metal
