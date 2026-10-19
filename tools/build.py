"""Build and verify the exact-build x86 adapter with an existing MSVC toolchain."""
from pathlib import Path
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import time
from laa import identity

ROOT=Path(__file__).resolve().parents[1]
SUPPORTED={'FFXi.dll':'760f8245173c85976ddf2b0828f90a11db6a2987e96982efc58df812dff5b2a4',
           'FFXiMain.dll':'042884888eea4fadac183e520f2ae9f8c4fa267860e685048e1880efd358e872'}

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()

def environment():
    finder=Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    install=subprocess.check_output([str(finder),'-latest','-products','*','-requires',
              'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True,timeout=20).strip()
    vcvars=Path(install)/'VC/Auxiliary/Build/vcvarsall.bat'
    command='cmd.exe /d /s /c ""'+str(vcvars)+'" x86 >nul && set"'
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    if result.returncode:raise RuntimeError('Existing x86 MSVC environment unavailable')
    env=os.environ.copy()
    for line in result.stdout.splitlines():
        if '=' not in line or line.startswith('='):continue
        key,value=line.split('=',1)
        if key.lower() not in {'path','include','lib','libpath'}:continue
        for old in list(env):
            if old.lower()==key.lower():del env[old]
        env[key]=value
    return env

def build(args):
    pol=args.pol.resolve(strict=True);windower=args.windower.resolve(strict=True)
    game=args.game.resolve(strict=True) if args.game else pol.parent.parent/'FINAL FANTASY XI'
    if not identity(pol.read_bytes())['large_address_aware']:
        raise RuntimeError('POL must already be LAA. Inspect/apply tools/laa.py while it is closed.')
    for name,digest in SUPPORTED.items():
        if sha(game/name)!=digest:raise RuntimeError('Unsupported engine build: '+name)
    required=[pol,game/'FFXi.dll',game/'FFXiMain.dll',windower/'Windower.exe',windower/'Hook.dll',pol.parent/'d3d8.dll']
    for path in required:
        if not path.is_file():raise FileNotFoundError(path)
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    (out/'receipts').mkdir();logs=out/'logs';logs.mkdir()
    binding='constexpr wchar_t kPolPath[] = L'+json.dumps(str(pol))+';\n'
    binding+='constexpr wchar_t kLogRoot[] = L'+json.dumps(str(logs))+';\nconstexpr unsigned kTargetMainMiB=1024u;\n'
    (out/'retail_binding.h').write_text(binding)
    (out/'arena.def').write_text('EXPORTS\nRetailArenaArm=_RetailArenaArm@4\nRetailArenaIsReady=_RetailArenaIsReady@0\nRetailArenaMeasuredBytes=_RetailArenaMeasuredBytes@0\nRetailArenaTargetBytes=_RetailArenaTargetBytes@0\n')
    (out/'gate.def').write_text('EXPORTS\nluaopen__RetailGate\n')
    env=environment();deadline=time.monotonic()+540
    search=next(value for key,value in env.items() if key.lower()=='path')
    compiler=shutil.which('cl.exe',path=search)
    if not compiler:raise RuntimeError('Existing x86 compiler unavailable')
    common=[compiler,'/nologo','/std:c++20','/O2','/MT','/W4','/WX','/EHsc','/I'+str(out)]
    def run(command,label):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Bounded build deadline reached')
        result=subprocess.run(command,cwd=out,env=env,capture_output=True,text=True,
            timeout=min(60,remaining),creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        (out/(label+'.log')).write_text(result.stdout+'\n'+result.stderr)
        if result.returncode:raise RuntimeError(label+' failed; inspect the local build log')
        return result
    def compile(name,source,extra=()):
        run(common+[str(ROOT/'native'/source),'/Fo'+str(out/(name+'.obj')),
            '/Fe'+str(out/name),*extra],name+'-build')
    compile('RetailArena.dll','retail_arena.cpp',['/LD','/link','/DEF:'+str(out/'arena.def'),'ole32.lib'])
    compile('retail-inject.exe','retail_inject.cpp')
    compile('_RetailGate.dll','retail_gate.cpp',['/LD','/link','/DEF:'+str(out/'gate.def')])
    compile('retail-arena-test.exe','retail_arena_test.cpp',['ole32.lib','uuid.lib'])
    native=json.loads(run([str(out/'retail-arena-test.exe')],'native-tests').stdout)
    stage=out/'staged-addon/retail_stress';(stage/'libs').mkdir(parents=True)
    shutil.copy2(out/'_RetailGate.dll',stage/'libs/_RetailGate.dll')
    expected=(pol.parent/'d3d8.dll').as_posix().lower()
    addon=(ROOT/'addon/retail_stress.lua.in').read_text().replace('@D3D8_PATH@',expected).replace('@ARENA_BYTES@','1073741696')
    (stage/'retail_stress.lua').write_text(addon)
    lua={'status':'not run; installed LuaCore and XIPivot are required'}
    core=windower/'plugins/LuaCore.dll';pivot=windower/'addons/XIPivot/XIPivot.lua'
    if core.is_file() and pivot.is_file():
        compile('retail-lua-test.exe','retail_lua_test.cpp')
        lua=json.loads(run([str(out/'retail-lua-test.exe'),str(core),str(ROOT/'tests/test_retail_gate.lua'),
            str(stage/'retail_stress.lua'),str(stage/'libs/_RetailGate.dll'),str(pivot),expected],'lua-tests').stdout)
    for name in ['arm_retail.py','launch_retail_stress.py']:
        shutil.copy2(ROOT/'tools'/name,out/name)
    pinned=required+[out/name for name in ['RetailArena.dll','retail-inject.exe','arm_retail.py','launch_retail_stress.py']]
    manifest={'pol_path':str(pol),'windower':str(windower),'target_main_mib':1024,
              'pins':[{'path':str(path),'sha256':sha(path)} for path in pinned]}
    (out/'install.json').write_text(json.dumps(manifest,indent=2))
    report={'native_tests':native,'lua_tests':lua,'game_startup_tested':False,
            'staged_addon':str(stage),'auto_launcher':str(out/'launch_retail_stress.py')}
    (out/'build-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pol',type=Path,required=True)
    parser.add_argument('--windower',type=Path,required=True)
    parser.add_argument('--game',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'local/build')
    args=parser.parse_args()
    ctypes.WinDLL('kernel32').SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    build(args)
