#pragma once
#include <windows.h>
#include <cstdint>
struct RetailPoolStats { uint32_t used{}, free{}, largest{}, blocks{}; bool valid{}; };
inline bool retailRead32(uintptr_t p,uint32_t& v) {
    SIZE_T got{};return ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(p),&v,4,&got)&&got==4;
}
inline RetailPoolStats inspectRetailPool(uint32_t first,uint32_t finish,uint32_t expected) {
    RetailPoolStats s;
    if(!first||finish<=first||uint64_t(finish)-first+16!=expected)return s;
    uint32_t cursor=first;
    while(cursor<finish&&s.blocks<32768) {
        uint32_t active{},next{};
        if(!retailRead32(uintptr_t(cursor)+4,active)||!retailRead32(uintptr_t(cursor)+8,next)||
           active>1||uint64_t(next)<uint64_t(cursor)+32||next>finish)return s;
        uint32_t payload=next-cursor-32;
        if(active)s.used+=payload;else{s.free+=payload;if(payload>s.largest)s.largest=payload;}
        ++s.blocks;cursor=next;
    }
    s.valid=cursor==finish;return s;
}
