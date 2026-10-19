local factory=assert(package.loadlib(gate_path,'luaopen__RetailGate'))
local real=factory()
local s=real.snapshot()
assert(s.injected==false and s.patched==false and s.arena_bytes==0 and s.pid>0)
assert(loadfile(pivot_path)) -- Shipped typo is repaired before installation.
local expected=assert(expected_d3d8)
local cases={
 {injected=false,patched=false,laa=true,arena_bytes=0,d3d8_path=expected,d3d11_loaded=true},
 {injected=true,patched=false,laa=true,arena_bytes=536870784,d3d8_path=expected,d3d11_loaded=true},
 {injected=true,patched=true,laa=true,arena_bytes=201326464,d3d8_path=expected,d3d11_loaded=true},
 {injected=true,patched=true,laa=true,arena_bytes=536870784,d3d8_path='C:\\Windows\\SysWOW64\\d3d8.dll',d3d11_loaded=true},
 {injected=true,patched=true,laa=false,arena_bytes=536870784,d3d8_path=expected,d3d11_loaded=true},
 {injected=true,patched=true,laa=true,arena_bytes=536870784,d3d8_path=expected,d3d11_loaded=false},
 {injected=true,patched=true,laa=true,arena_bytes=536870784,d3d8_path=expected,d3d11_loaded=true},
 {injected=true,patched=true,laa=true,arena_bytes=1073741696,target_arena_bytes=1073741696,d3d8_path=expected,d3d11_loaded=true},
 {injected=true,patched=true,laa=true,arena_bytes=536870784,target_arena_bytes=1073741696,d3d8_path=expected,d3d11_loaded=true},
}
local original_open=io.open
for index,status in ipairs(cases) do
 local commands,events,writes={},{},{}
 coroutine.schedule=function(f)f()end
 status.pid=s.pid
 status.target_arena_bytes=status.target_arena_bytes or 536870784
 package.loaded._RetailGate={snapshot=function()return status end}
 _addon={}
 windower={addon_path='F:/mock/',windower_path='F:/mock/',
  ffxi={get_info=function()return {zone=241,logged_in=true} end},
  send_command=function(c)commands[#commands+1]=c end,
  add_to_chat=function()end,
  register_event=function(k,f)events[k]=f end}
 io.open=function()return {write=function(_,line)writes[#writes+1]=line end,close=function()end}end
 assert(loadfile(addon_path))()
 assert(#commands==(index==8 and 1 or 0),'gate case '..index)
 if #commands==1 then assert(commands[1]=='lua load XIPivot') end
 assert(writes[1]:find('"zone_id":241',1,true))
 events['addon command'](); events.login(); events['zone change']()
end
io.open=original_open
print('{"actual_windower_lua51_bridge":"passed","overlay_gate_cases_passed":9,"retail_game_tested":false}')
