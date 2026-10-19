#include "retail_arena.cpp"
#include <cassert>
#include "retail_pool.h"
int main() {
    assert(retailProcessAudio(true));assert(retailProcessAudio(false));
    auto sample=static_cast<unsigned char*>(VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    assert(sample);
    uint32_t first=static_cast<uint32_t>(reinterpret_cast<uintptr_t>(sample));
    *reinterpret_cast<uint32_t*>(sample+4)=1;*reinterpret_cast<uint32_t*>(sample+8)=first+128;
    *reinterpret_cast<uint32_t*>(sample+132)=0;*reinterpret_cast<uint32_t*>(sample+136)=first+240;
    auto stats=inspectRetailPool(first,first+240,256);
    assert(stats.valid&&stats.used==96&&stats.free==80&&stats.largest==80&&stats.blocks==2);
    assert(!inspectRetailPool(first,first+240,512).valid);
    *reinterpret_cast<uint32_t*>(sample+132)=2;assert(!inspectRetailPool(first,first+240,256).valid);
    *reinterpret_cast<uint32_t*>(sample+132)=0;*reinterpret_cast<uint32_t*>(sample+136)=first;
    assert(!inspectRetailPool(first,first+240,256).valid);VirtualFree(sample,0,MEM_RELEASE);
    auto image = reinterpret_cast<uintptr_t>(VirtualAlloc(nullptr, 0x460000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    assert(image);
    auto bytes = reinterpret_cast<unsigned char*>(image);
    uint32_t pe = 0x100, stamp = 0x6ac37846;
    std::memcpy(bytes + 0x3c, &pe, 4); std::memcpy(bytes + pe + 8, &stamp, 4);
    std::memcpy(bytes + 0x292d2, signature, sizeof(signature));
    *reinterpret_cast<uint32_t*>(bytes + 0x4570b4) = 1;
    assert(!expand(image)); // Every initialized-pool slot is refused.
    *reinterpret_cast<uint32_t*>(bytes + 0x4570b4) = 0;
    for (int i = 0; i < 10; ++i) {
        *reinterpret_cast<uint32_t*>(bytes + 0x4570b4 + i*4) = 1;
        assert(!expand(image));
        *reinterpret_cast<uint32_t*>(bytes + 0x4570b4 + i*4) = 0;
    }
    bytes[0x292d2] ^= 1; assert(!expand(image)); bytes[0x292d2] ^= 1;
    bytes[pe + 8] ^= 1; assert(!expand(image)); bytes[pe + 8] ^= 1;
    assert(expand(image)); assert(!expand(image)); // No second patch.
    assert(*reinterpret_cast<uint32_t*>(bytes + 0x292ed) == (kTargetMainMiB-128u)*1048576u);
    assert(*reinterpret_cast<uint32_t*>(bytes + 0x292f3) == (kTargetMainMiB-102u)*1048576u+8192u);
    for (size_t i = 0; i < sizeof(signature); ++i)
        if (!(i >= 27 && i < 31) && !(i >= 33 && i < 37)) assert(bytes[0x292d2+i] == signature[i]);
    VirtualFree(bytes, 0, MEM_RELEASE);
    auto slot = findImport(GetModuleHandleW(nullptr), "ole32.dll", "CoCreateInstance");
    assert(slot); polSlot = slot; polOriginal = *slot;
    assert(swap(slot, polOriginal, reinterpret_cast<void*>(&polCreate)));
    LPVOID object{};
    HRESULT hr = CoCreateInstance(GUID_NULL, nullptr, CLSCTX_INPROC_SERVER, IID_IUnknown, &object);
    assert(FAILED(hr));
    assert(swap(slot, reinterpret_cast<void*>(&polCreate), polOriginal));
    assert(!RetailArenaIsReady());
    assert(!RetailArenaArm(nullptr)); // Test executable cannot arm the retail adapter.
    std::puts("{\"native_guard_and_iat_tests\":\"passed\",\"game_startup_tested\":false}");
}
