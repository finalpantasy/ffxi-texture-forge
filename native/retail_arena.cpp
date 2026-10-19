// Opt-in retail startup adapter. Never moves an initialized arena.
// Derived from the qualified arena_preload.cpp experiment; no Ashita ABI.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objbase.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "retail_binding.h"
#include "retail_mute.h"

namespace {
using Create = HRESULT (WINAPI*)(REFCLSID, LPUNKNOWN, DWORD, REFIID, LPVOID*);
void** polSlot{}; void* polOriginal{};
void** entrySlot{}; void* entryOriginal{};
volatile LONG ready{}, attempted{};
HANDLE journal = INVALID_HANDLE_VALUE;
const unsigned char signature[] = {
    0x3d,0x00,0x01,0x00,0x00,0x7e,0x07,0xc7,0x46,0x04,0x00,0x01,0x00,0x00,
    0x8b,0x46,0x04,0x2d,0x80,0x00,0x00,0x00,0xc1,0xe0,0x14,
    0x8d,0xb8,0x00,0x00,0x00,0x04,0x8d,0x88,0x00,0x20,0xa0,0x05};

bool read(uintptr_t p, void* out, SIZE_T n) {
    SIZE_T got{};
    return ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(p), out, n, &got) && got == n;
}
void record(const char* phase, const char* error = "") {
    if (journal == INVALID_HANDLE_VALUE) return;
    char line[1024]; DWORD written{};
    int n = std::snprintf(line, sizeof(line),
        "{\"pid\":%lu,\"tick_ms\":%llu,\"phase\":\"%s\",\"error\":\"%s\",\"ready\":%s,"
        "\"target_main_mib\":%u,\"pol_hook_active\":%s,\"entry_hook_active\":%s}\n",
        GetCurrentProcessId(), GetTickCount64(), phase, error, ready ? "true" : "false",
        kTargetMainMiB,
        polSlot && *polSlot != polOriginal ? "true" : "false",
        entrySlot && *entrySlot != entryOriginal ? "true" : "false");
    if (n > 0 && n < int(sizeof(line))) {
        WriteFile(journal, line, DWORD(n), &written, nullptr); FlushFileBuffers(journal);
    }
}
bool swap(void** slot, void* expected, void* replacement) {
    DWORD old{}, ignored{};
    if (!slot || !VirtualProtect(slot, sizeof(void*), PAGE_READWRITE, &old)) return false;
    bool changed = InterlockedCompareExchangePointer(slot, replacement, expected) == expected;
    bool restored = VirtualProtect(slot, sizeof(void*), old, &ignored) != FALSE;
    return changed && restored && *slot == replacement;
}
void** findImport(HMODULE module, const char* library, const char* function, DWORD stamp = 0) {
    auto base = reinterpret_cast<uintptr_t>(module);
    IMAGE_DOS_HEADER dos{}; IMAGE_NT_HEADERS32 nt{};
    if (!base || !read(base, &dos, sizeof(dos)) || dos.e_magic != IMAGE_DOS_SIGNATURE ||
        dos.e_lfanew < 64 || dos.e_lfanew > 1048576 || !read(base + dos.e_lfanew, &nt, sizeof(nt)) ||
        nt.Signature != IMAGE_NT_SIGNATURE || nt.FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        (stamp && stamp != nt.FileHeader.TimeDateStamp)) return nullptr;
    auto rva = nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return nullptr;
    void** found{};
    auto desc = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base + rva);
    for (unsigned d = 0; d < 128 && desc[d].Name; ++d) {
        if (_stricmp(reinterpret_cast<const char*>(base + desc[d].Name), library) || !desc[d].OriginalFirstThunk) continue;
        auto names = reinterpret_cast<IMAGE_THUNK_DATA32*>(base + desc[d].OriginalFirstThunk);
        auto addresses = reinterpret_cast<IMAGE_THUNK_DATA32*>(base + desc[d].FirstThunk);
        for (unsigned i = 0; i < 4096 && names[i].u1.AddressOfData; ++i) {
            if (IMAGE_SNAP_BY_ORDINAL32(names[i].u1.Ordinal)) continue;
            auto name = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base + names[i].u1.AddressOfData);
            if (!std::strcmp(reinterpret_cast<const char*>(name->Name), function)) {
                if (found) return nullptr;
                found = reinterpret_cast<void**>(&addresses[i].u1.Function);
            }
        }
    }
    return found;
}
bool expand(uintptr_t image) {
    uint32_t offset{}, stamp{}, pools[10]{};
    if (!read(image + 0x3c, &offset, 4) || offset > 1048576 ||
        !read(image + offset + 8, &stamp, 4) || stamp != 0x6ac37846 ||
        !read(image + 0x4570b4, pools, sizeof(pools))) return false;
    for (auto p : pools) if (p) return false;
    unsigned char observed[sizeof(signature)]{};
    if (!read(image + 0x292d2, observed, sizeof(observed)) || std::memcmp(observed, signature, sizeof(signature))) return false;
    auto code = reinterpret_cast<unsigned char*>(image + 0x292d2);
    DWORD old{}, ignored{};
    if (!VirtualProtect(code, sizeof(signature), PAGE_EXECUTE_READWRITE, &old)) return false;
    constexpr uint32_t mainBase = (kTargetMainMiB - 128u) * 1048576u;
    constexpr uint32_t totalBase = mainBase + 26u * 1048576u + 8192u;
    std::memcpy(code + 27, &mainBase, 4); std::memcpy(code + 33, &totalBase, 4);
    unsigned char expected[sizeof(signature)]; std::memcpy(expected, signature, sizeof(signature));
    std::memcpy(expected + 27, &mainBase, 4); std::memcpy(expected + 33, &totalBase, 4);
    bool ok = read(image + 0x292d2, observed, sizeof(observed)) && !std::memcmp(observed, expected, sizeof(expected));
    if (!ok) std::memcpy(code, signature, sizeof(signature));
    bool protectedAgain = VirtualProtect(code, sizeof(signature), old, &ignored) != FALSE;
    bool flushed = FlushInstructionCache(GetCurrentProcess(), code, sizeof(signature)) != FALSE;
    return ok && protectedAgain && flushed;
}
HRESULT WINAPI entryCreate(REFCLSID clsid, LPUNKNOWN outer, DWORD context, REFIID iid, LPVOID* object) {
    auto original = reinterpret_cast<Create>(entryOriginal);
    HRESULT result = original(clsid, outer, context, iid, object);
    DWORD error = GetLastError();
    auto image = reinterpret_cast<uintptr_t>(GetModuleHandleW(L"FFXiMain.dll"));
    uint32_t firstInstruction{};
    bool unpacked = image && read(image + 0x292d2, &firstInstruction, 4) && firstInstruction == 0x0001003d;
    if (SUCCEEDED(result) && unpacked && !InterlockedCompareExchange(&attempted, 1, 0)) {
        bool patched = expand(image);
        bool restored = swap(entrySlot, reinterpret_cast<void*>(&entryCreate), entryOriginal);
        if (patched && restored && polSlot && *polSlot == polOriginal) InterlockedExchange(&ready, 1);
        record("inner-com-return", !patched ? "preinit-signature-or-pools-refused" : !restored ? "hook-restore-failed" : "");
    }
    SetLastError(error); return result;
}
HRESULT WINAPI polCreate(REFCLSID clsid, LPUNKNOWN outer, DWORD context, REFIID iid, LPVOID* object) {
    auto original = reinterpret_cast<Create>(polOriginal);
    HRESULT result = original(clsid, outer, context, iid, object);
    DWORD error = GetLastError();
    auto entry = GetModuleHandleW(L"FFXi.dll");
    if (SUCCEEDED(result) && entry && !entrySlot) {
        entrySlot = findImport(entry, "ole32.dll", "CoCreateInstance", 0x6ac37836);
        bool installed = false;
        if (entrySlot) {
            entryOriginal = *entrySlot;
            installed = swap(entrySlot, entryOriginal, reinterpret_cast<void*>(&entryCreate));
        }
        bool restored = swap(polSlot, reinterpret_cast<void*>(&polCreate), polOriginal);
        record("entry-import-armed", !installed ? "entry-import-unavailable" : !restored ? "pol-hook-restore-failed" : "");
    }
    SetLastError(error); return result;
}
}

extern "C" __declspec(dllexport) DWORD WINAPI RetailArenaArm(void*) {
    wchar_t exe[2048]{}, log[2048]{};
    if (!GetModuleFileNameW(nullptr, exe, 2048) || _wcsicmp(exe, kPolPath) ||
        polSlot || GetModuleHandleW(L"FFXi.dll") || GetModuleHandleW(L"FFXiMain.dll")) return 0;
    auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    IMAGE_DOS_HEADER dos{}; WORD flags{};
    if (!read(base, &dos, sizeof(dos)) || !read(base + dos.e_lfanew + 22, &flags, 2) || !(flags & 0x20)) return 0;
    if (swprintf_s(log, L"%s\\retail-arena-%lu-%llu.jsonl", kLogRoot, GetCurrentProcessId(), GetTickCount64()) < 0) return 0;
    journal = CreateFileW(log, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (journal == INVALID_HANDLE_VALUE) return 0;
    if(!retailProcessAudio(true)){record("arm-refused","process-audio-mute-failed");return 0;}
    record("process-audio-muted");
    polSlot = findImport(GetModuleHandleW(nullptr), "ole32.dll", "CoCreateInstance");
    if (!polSlot) { record("arm-refused", "pol-import-unavailable"); return 0; }
    polOriginal = *polSlot;
    bool installed = swap(polSlot, polOriginal, reinterpret_cast<void*>(&polCreate));
    record("pol-import-armed", installed ? "" : "pol-import-write-failed");
    return installed ? 1 : 0;
}
extern "C" __declspec(dllexport) DWORD WINAPI RetailArenaIsReady() { return DWORD(ready); }
extern "C" __declspec(dllexport) DWORD WINAPI RetailArenaMeasuredBytes() {
    if (!ready) return 0;
    auto image = reinterpret_cast<uintptr_t>(GetModuleHandleW(L"FFXiMain.dll"));
    uint32_t first{}, finish{};
    if (!image || !read(image + 0x4570b4, &first, 4) || !read(image + 0x4570b8, &finish, 4) ||
        !first || finish <= first || finish - first + 16 != kTargetMainMiB*1048576u-128u) return 0;
    return finish - first + 16;
}
extern "C" __declspec(dllexport) DWORD WINAPI RetailArenaTargetBytes() { return kTargetMainMiB*1048576u-128u; }
BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) { return TRUE; }
