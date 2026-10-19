"""Explicit user action: arm a single retail POL before choosing Play. Does not launch/login."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys, time

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def arm(root, pid=None):
    manifest=json.loads((root/'install.json').read_text(encoding='utf-8'))
    for item in manifest['pins']:
        if sha(item['path'])!=item['sha256']:raise RuntimeError('File changed; recheck installation: '+item['path'])
    if manifest.get('pressure_payload_mib'):
        import xml.etree.ElementTree as ET
        settings=ET.parse(Path(manifest['windower'])/'addons/XIPivot/data/settings.xml').getroot()
        overlays=(settings.findtext('global/overlays') or '').split(',')
        expected='Windurst-'+str(manifest['pressure_payload_mib'])+'MiB-Stress'
        if not overlays or overlays[0].strip()!=expected or (settings.findtext('global/cache_enabled') or '').strip().lower()!='false':
            raise RuntimeError('Pressure overlay configuration changed; refused to arm.')
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process -Filter \"Name='pol.exe'\" | Select-Object ProcessId,ExecutablePath,CreationDate) | ConvertTo-Json -Compress"],
        capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Could not inspect retail POL process')
    rows=json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(rows,dict):rows=[rows]
    matches=[p for p in rows if str(p.get('ExecutablePath','')).lower()==manifest['pol_path'].lower() and (pid is None or p['ProcessId']==pid)]
    if len(matches)!=1:raise RuntimeError('Start your configured Windower client and stay in PlayOnline before selecting Play. Exactly one matching retail POL is required.')
    selected=matches[0]
    command=[str(root/'retail-inject.exe'),str(selected['ProcessId']),str(root/'RetailArena.dll')]
    r=subprocess.run(command,text=True,capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    receipt={'pid':selected['ProcessId'],'process_created':selected['CreationDate'],'exit_code':r.returncode,
             'stdout':r.stdout,'stderr':r.stderr,'timestamp':time.time(),
             'scope':'Early hook only. Expanded pool and renderer are measured by the in-client gate before loading textures.'}
    log=root/'receipts';log.mkdir(exist_ok=True)
    (log/('arm-'+str(selected['ProcessId'])+'-'+str(time.time_ns())+'.json')).write_text(json.dumps(receipt,indent=2))
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode:raise RuntimeError('Retail test not armed. Large texture overlay stays disabled.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pid',type=int)
    args=parser.parse_args()
    try:arm(Path(__file__).resolve().parent,args.pid)
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
