// Explicitly arm one user-selected, pre-FFXI retail POL PID. Never scans/injects by name.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <string>
#include "retail_binding.h"

uintptr_t remoteModule(DWORD pid, const wchar_t* name) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
    if (snapshot == INVALID_HANDLE_VALUE) return 0;
    MODULEENTRY32W entry{}; entry.dwSize = sizeof(entry); uintptr_t found{};
    if (Module32FirstW(snapshot, &entry)) do {
        if (!_wcsicmp(entry.szModule, name)) { found = reinterpret_cast<uintptr_t>(entry.modBaseAddr); break; }
    } while (Module32NextW(snapshot, &entry));
    CloseHandle(snapshot); return found;
}
int wmain(int argc, wchar_t** argv) {
    if (argc != 3) { std::fputs("Usage: retail-inject PID ABSOLUTE_DLL\n", stderr); return 2; }
    wchar_t* end{}; auto number = wcstoul(argv[1], &end, 10);
    if (!number || !end || *end || number == GetCurrentProcessId()) return 2;
    DWORD pid = number;
    HANDLE process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ, FALSE, pid);
    if (!process) return 3;
    wchar_t path[2048]{}; DWORD chars = 2048;
    if (!QueryFullProcessImageNameW(process, 0, path, &chars) || _wcsicmp(path, kPolPath) ||
        remoteModule(pid, L"FFXi.dll") || remoteModule(pid, L"FFXiMain.dll") || remoteModule(pid, L"RetailArena.dll")) {
        std::fputs("Refused: wrong executable, already armed, or FFXI already started.\n", stderr); CloseHandle(process); return 4;
    }
    auto local = LoadLibraryExW(argv[2], nullptr, DONT_RESOLVE_DLL_REFERENCES);
    auto arm = local ? GetProcAddress(local, "RetailArenaArm") : nullptr;
    if (!arm) { CloseHandle(process); return 5; }
    uintptr_t armRva = reinterpret_cast<uintptr_t>(arm) - reinterpret_cast<uintptr_t>(local);
    FreeLibrary(local);
    auto load = GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW");
    MEMORY_BASIC_INFORMATION info{}; wchar_t systemPath[2048]{};
    if (!load || !VirtualQuery(reinterpret_cast<void*>(load), &info, sizeof(info)) ||
        !GetModuleFileNameW(static_cast<HMODULE>(info.AllocationBase), systemPath, 2048)) { CloseHandle(process); return 6; }
    auto basename = wcsrchr(systemPath, L'\\');
    auto systemRemote = remoteModule(pid, basename ? basename + 1 : systemPath);
    if (!systemRemote) { CloseHandle(process); return 7; }
    uintptr_t remoteLoad = systemRemote + reinterpret_cast<uintptr_t>(load) - reinterpret_cast<uintptr_t>(info.AllocationBase);
    SIZE_T bytes = (wcslen(argv[2]) + 1) * sizeof(wchar_t), written{};
    auto memory = VirtualAllocEx(process, nullptr, bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!memory || !WriteProcessMemory(process, memory, argv[2], bytes, &written) || written != bytes) { CloseHandle(process); return 8; }
    HANDLE thread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteLoad), memory, 0, nullptr);
    if (!thread) { VirtualFreeEx(process, memory, 0, MEM_RELEASE); CloseHandle(process); return 9; }
    DWORD module{};
    if (WaitForSingleObject(thread, 15000) != WAIT_OBJECT_0 || !GetExitCodeThread(thread, &module) || !module) {
        // Keep remote string memory alive if the loader thread timed out.
        CloseHandle(thread); CloseHandle(process); return 10;
    }
    CloseHandle(thread); VirtualFreeEx(process, memory, 0, MEM_RELEASE);
    thread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(module + armRva), nullptr, 0, nullptr);
    DWORD result{};
    bool ok = thread && WaitForSingleObject(thread, 15000) == WAIT_OBJECT_0 && GetExitCodeThread(thread, &result) && result == 1;
    if (thread) CloseHandle(thread);
    CloseHandle(process);
    std::puts(ok ? "Early retail hook ARMED. Now choose Play in POL. Expansion is verified separately at FFXI startup." : "Adapter did not arm. Giant overlay will remain disabled.");
    return ok ? 0 : 11;
}
