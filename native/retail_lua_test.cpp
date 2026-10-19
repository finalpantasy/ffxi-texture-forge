#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
struct lua_State;
int main(int argc,char** argv) {
    if(argc!=7)return 2;
    auto module=LoadLibraryA(argv[1]);
    if(!module)return 3;
    auto state=reinterpret_cast<lua_State* (__cdecl*)()>(GetProcAddress(module,"luaL_newstate"))();
    if(!state)return 4;
    auto open=reinterpret_cast<void (__cdecl*)(lua_State*)>(GetProcAddress(module,"luaL_openlibs"));
    auto push=reinterpret_cast<void (__cdecl*)(lua_State*,const char*)>(GetProcAddress(module,"lua_pushstring"));
    auto field=reinterpret_cast<void (__cdecl*)(lua_State*,int,const char*)>(GetProcAddress(module,"lua_setfield"));
    auto load=reinterpret_cast<int (__cdecl*)(lua_State*,const char*)>(GetProcAddress(module,"luaL_loadfile"));
    auto call=reinterpret_cast<int (__cdecl*)(lua_State*,int,int,int)>(GetProcAddress(module,"lua_pcall"));
    auto error=reinterpret_cast<const char* (__cdecl*)(lua_State*,int,size_t*)>(GetProcAddress(module,"lua_tolstring"));
    auto close=reinterpret_cast<void (__cdecl*)(lua_State*)>(GetProcAddress(module,"lua_close"));
    if(!open||!push||!field||!load||!call||!error||!close)return 5;
    open(state);
    push(state,argv[3]);field(state,-10002,"addon_path");
    push(state,argv[4]);field(state,-10002,"gate_path");
    push(state,argv[5]);field(state,-10002,"pivot_path");
    push(state,argv[6]);field(state,-10002,"expected_d3d8");
    int result=load(state,argv[2]);if(!result)result=call(state,0,0,0);
    if(result)std::fprintf(stderr,"%s\n",error(state,-1,nullptr));
    close(state);FreeLibrary(module);return result?1:0;
}
