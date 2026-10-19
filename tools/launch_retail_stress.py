"""One-click retail launch: own a new Windower child, then arm its new POL only."""
from pathlib import Path
import ctypes,json,os,subprocess,sys,time
from ctypes import wintypes as w
from arm_retail import arm,sha

class ProcessEntry(ctypes.Structure):
    _fields_=[('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',ctypes.c_size_t),
              ('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),('priority',w.LONG),
              ('flags',w.DWORD),('exe',w.WCHAR*260)]

def snapshot():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
    k.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(ProcessEntry)];k.Process32FirstW.restype=w.BOOL
    k.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(ProcessEntry)];k.Process32NextW.restype=w.BOOL
    k.CloseHandle.argtypes=[w.HANDLE]
    h=k.CreateToolhelp32Snapshot(2,0)
    if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    rows=[];e=ProcessEntry();e.size=ctypes.sizeof(e)
    try:
        ok=k.Process32FirstW(h,ctypes.byref(e))
        while ok:
            rows.append({'pid':int(e.pid),'parent':int(e.parent),'exe':e.exe})
            ok=k.Process32NextW(h,ctypes.byref(e))
    finally:k.CloseHandle(h)
    return rows

def executable(pid):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    k.CloseHandle.argtypes=[w.HANDLE]
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return None
    try:
        buf=ctypes.create_unicode_buffer(32768);n=w.DWORD(len(buf))
        return buf.value if k.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(n)) else None
    finally:k.CloseHandle(h)

def eligible_children(rows,before,owner_pid,pol_path,path_for=executable):
    candidates=[]
    for p in rows:
        if p['pid'] in before or p['parent']!=owner_pid or p['exe'].lower()!='pol.exe':continue
        actual=path_for(p['pid'])
        if actual and actual.lower()==pol_path.lower():candidates.append(p['pid'])
    if len(candidates)>1:raise RuntimeError('Multiple new POL children; refused to choose a client.')
    return candidates

def require_fresh(rows,windower,pol,path_for=executable):
    for p in rows:
        if p['exe'].lower() not in ('pol.exe','windower.exe'):continue
        actual=path_for(p['pid'])
        if actual and actual.lower() in (str(windower).lower(),pol.lower()):
            raise RuntimeError('Close this retail game and Windower launcher, then use the test shortcut again. Other clients were not touched.')

def elevate():
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.IsUserAnAdmin.restype=w.BOOL
    if shell.IsUserAnAdmin():return False
    shell.ShellExecuteW.argtypes=[w.HWND,w.LPCWSTR,w.LPCWSTR,w.LPCWSTR,w.LPCWSTR,ctypes.c_int]
    shell.ShellExecuteW.restype=ctypes.c_void_p
    pythonw=Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.is_file():pythonw=Path(sys.executable)
    result=shell.ShellExecuteW(None,'runas',str(pythonw),subprocess.list2cmdline([str(Path(__file__).resolve())]),str(Path(__file__).resolve().parent),0)
    if not result or result<=32:raise RuntimeError('Administrator launch was declined or unavailable; nothing was armed.')
    return True

def launch(root):
    m=json.loads((root/'install.json').read_text());windower=Path(m['windower'])/'Windower.exe'
    for p in m['pins']:
        if sha(p['path'])!=p['sha256']:raise RuntimeError('Test file changed: '+p['path'])
    rows=snapshot();require_fresh(rows,windower,m['pol_path']);before={p['pid'] for p in rows}
    child=subprocess.Popen([str(windower)],cwd=windower.parent,creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    # Only the exact launcher handle created here authorizes child selection.
    deadline=time.monotonic()+540
    while time.monotonic()<deadline:
        candidates=eligible_children(snapshot(),before,child.pid,m['pol_path'])
        if candidates:
            arm(root,candidates[0])
            return {'launcher_pid':child.pid,'client_pid':candidates[0],'armed':True,'time':time.time()}
        if child.poll() is not None:raise RuntimeError('The owned Windower launcher exited before a POL child was armed. Its game was not modified.')
        time.sleep(.2)
    raise RuntimeError('No retail client was launched within nine minutes. Relaunch using the test shortcut when ready.')

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    mutex=None
    try:
        if elevate():sys.exit(0)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,w.BOOL,w.LPCWSTR];kernel.CreateMutexW.restype=w.HANDLE
        kernel.CloseHandle.argtypes=[w.HANDLE]
        mutex=kernel.CreateMutexW(None,False,'Local\\FFXI-Texture-Forge')
        if not mutex or ctypes.get_last_error()==183:raise RuntimeError('The automatic test launcher is already running.')
        result=launch(root)
        p=root/'receipts';p.mkdir(exist_ok=True)
        (p/('automatic-'+str(time.time_ns())+'.json')).write_text(json.dumps(result,indent=2))
    except Exception as e:
        if mutex:
            kernel.CloseHandle(mutex); mutex=None
        p=root/'receipts';p.mkdir(exist_ok=True)
        (p/('launch-error-'+str(time.time_ns())+'.json')).write_text(json.dumps({'error':str(e),'time':time.time()},indent=2))
        ctypes.windll.user32.MessageBoxW(None,str(e),'FFXI Texture Forge',0x10)
        sys.exit(1)
    finally:
        if mutex:kernel.CloseHandle(mutex)
