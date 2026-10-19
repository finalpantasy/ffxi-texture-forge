// Read-only Lua 5.1 bridge for Windower's actual LuaCore (which is not LuaJIT).
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <psapi.h>
#include "retail_pool.h"
struct lua_State;
using CFunction = int (__cdecl*)(lua_State*);
namespace {
using CreateTable = void (__cdecl*)(lua_State*, int, int);
using PushNumber = void (__cdecl*)(lua_State*, double);
using PushBoolean = void (__cdecl*)(lua_State*, int);
using PushString = void (__cdecl*)(lua_State*, const char*);
using SetField = void (__cdecl*)(lua_State*, int, const char*);
using PushClosure = void (__cdecl*)(lua_State*, CFunction, int);
CreateTable createTable{}; PushNumber pushNumber{}; PushBoolean pushBoolean{};
PushString pushString{}; SetField setField{}; PushClosure pushClosure{};
void number(lua_State* L, const char* key, double value) { pushNumber(L,value); setField(L,-2,key); }
void boolean(lua_State* L, const char* key, bool value) { pushBoolean(L,value); setField(L,-2,key); }
void modulePath(lua_State* L, const char* key, const wchar_t* module) {
    wchar_t path[2048]{}; char utf8[8192]{};
    auto handle=GetModuleHandleW(module);
    if (handle && GetModuleFileNameW(handle,path,2048)) WideCharToMultiByte(CP_UTF8,0,path,-1,utf8,8192,nullptr,nullptr);
    pushString(L,utf8); setField(L,-2,key);
}
int __cdecl snapshot(lua_State* L) {
    createTable(L,0,20);
    auto module=GetModuleHandleW(L"RetailArena.dll");
    using Status=DWORD (WINAPI*)();
    auto ready=module?reinterpret_cast<Status>(GetProcAddress(module,"RetailArenaIsReady")):nullptr;
    auto measured=module?reinterpret_cast<Status>(GetProcAddress(module,"RetailArenaMeasuredBytes")):nullptr;
    auto target=module?reinterpret_cast<Status>(GetProcAddress(module,"RetailArenaTargetBytes")):nullptr;
    number(L,"pid",GetCurrentProcessId());
    boolean(L,"injected",module!=nullptr); boolean(L,"patched",ready && ready()!=0);
    number(L,"arena_bytes",measured?measured():0);
    number(L,"target_arena_bytes",target?target():0);
    auto image=reinterpret_cast<uintptr_t>(GetModuleHandleW(L"FFXiMain.dll"));
    uint32_t first{},finish{};RetailPoolStats pool;
    if(image&&measured&&measured()&&retailRead32(image+0x4570b4,first)&&retailRead32(image+0x4570b8,finish))
        pool=inspectRetailPool(first,finish,measured());
    boolean(L,"pool_chain_valid",pool.valid);
    if(pool.valid){number(L,"used_payload_bytes",pool.used);number(L,"free_payload_bytes",pool.free);number(L,"largest_free_payload_bytes",pool.largest);number(L,"pool_blocks",pool.blocks);}
    auto base=reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    boolean(L,"laa",(nt->FileHeader.Characteristics&0x20)!=0);
    PROCESS_MEMORY_COUNTERS_EX memory{};memory.cb=sizeof(memory);
    using MemoryInfo=BOOL(WINAPI*)(HANDLE,PPROCESS_MEMORY_COUNTERS,DWORD);
    auto getMemory=reinterpret_cast<MemoryInfo>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"K32GetProcessMemoryInfo"));
    if(getMemory&&getMemory(GetCurrentProcess(),reinterpret_cast<PPROCESS_MEMORY_COUNTERS>(&memory),sizeof(memory)))
        number(L,"private_bytes",double(memory.PrivateUsage));
    uint64_t cursor{},freeVA{},largest{};MEMORY_BASIC_INFORMATION region{};
    for(unsigned i=0;i<65536&&cursor<0xffff0000ull;++i){
        if(!VirtualQuery(reinterpret_cast<void*>(static_cast<uintptr_t>(cursor)),&region,sizeof(region)))break;
        if(region.State==MEM_FREE){freeVA+=region.RegionSize;if(region.RegionSize>largest)largest=region.RegionSize;}
        uint64_t next=uint64_t(reinterpret_cast<uintptr_t>(region.BaseAddress))+region.RegionSize;
        if(next<=cursor)break;cursor=next;
    }
    number(L,"free_address_bytes",double(freeVA));number(L,"largest_free_address_block",double(largest));
    modulePath(L,"d3d8_path",L"d3d8.dll");
    boolean(L,"d3d11_loaded",GetModuleHandleW(L"d3d11.dll")!=nullptr);
    boolean(L,"d3d12_loaded",GetModuleHandleW(L"d3d12.dll")!=nullptr);
    return 1;
}
}
extern "C" __declspec(dllexport) int __cdecl luaopen__RetailGate(lua_State* L) {
    auto core=GetModuleHandleW(L"LuaCore.dll");
    if (!core) return 0;
    createTable=reinterpret_cast<CreateTable>(GetProcAddress(core,"lua_createtable"));
    pushNumber=reinterpret_cast<PushNumber>(GetProcAddress(core,"lua_pushnumber"));
    pushBoolean=reinterpret_cast<PushBoolean>(GetProcAddress(core,"lua_pushboolean"));
    pushString=reinterpret_cast<PushString>(GetProcAddress(core,"lua_pushstring"));
    setField=reinterpret_cast<SetField>(GetProcAddress(core,"lua_setfield"));
    pushClosure=reinterpret_cast<PushClosure>(GetProcAddress(core,"lua_pushcclosure"));
    if (!createTable||!pushNumber||!pushBoolean||!pushString||!setField||!pushClosure) return 0;
    createTable(L,0,1); pushClosure(L,snapshot,0); setField(L,-2,"snapshot");
    return 1;
}
