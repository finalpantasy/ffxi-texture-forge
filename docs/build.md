# Build and local testing

Use 64-bit Windows, an existing Visual Studio C++ toolchain with x86 compiler
and Windows SDK, and Python 3. The native build installs no dependencies. NumPy
is needed only for the optional fixture generator (`requirements.txt`).

The adapter is intentionally pinned to the engine hashes in
`supported-build.json`. An update requires new analysis, not removing the check.
Build while the game is closed. Use a separate portable Windower test copy so
normal startup and addons remain intact.

```powershell
python tools/build.py --pol 'D:/Games/SquareEnix/PlayOnlineViewer/pol.exe' --windower 'D:/Windower-Test'
```

Supply `--game` if the game directory is not the sibling `FINAL FANTASY XI`.
The output defaults to ignored `local/build/` and refuses an existing output
directory. POL must already be LAA; `python tools/laa.py PATH` inspects without
changing it. Applying LAA is an explicit separate command with backup evidence.
The configured renderer DLL must already exist beside POL. The live addon
requires that exact path and D3D11 loaded; the build does not download a wrapper.

The build runs native guards, pool accounting and import restoration tests. If
the supplied Windower has LuaCore and XIPivot installed, it also runs nine gate
cases against the actual local LuaCore. A skipped Lua test is not a pass.

Copy the generated `local/build/staged-addon/retail_stress` directory into the
**test copy's** `addons` directory. Install XIPivot separately from its upstream
project and configure only your intended test overlays, with its file cache off.
Add this block to that test copy's `scripts/init.txt` after its display setup:

```text
load LuaCore;
wait 3;
lua load retail_stress;
```

Do not also autoload XIPivot before this gate. The native adapter must be armed
before selecting Play, and the addon only requests XIPivot after confirming the
expanded pool, LAA and the configured DX11 wrapper.

```powershell
pythonw local/build/launch_retail_stress.py
```

The helper opens Windower and arms only its own new POL child. You choose the
profile and handle login. It may request elevation to match the launcher. It
refuses an existing matching client or launcher; do not attach it to an already
loaded game. The helper times out after nine minutes. No login is automated.

Native early-hook receipts are in `local/build/logs`. Loaded Lua receipts are
in the test Windower's `logs` directory. Confirm a valid *loaded* pool sample,
not the early zone-change event; the latter often precedes asset loading.
Test login, movement, zoning out/back, and a full minute after returning.
Keep the original fixture and test profile available for recovery.

## Pressure fixtures

The generator writes a new file and refuses to overwrite its target:

```powershell
python tools/fixture.py 'D:/LocalSources/80.DAT' 'D:/TestOutput/80.DAT' --payload-mib 768
```

It enlarges supported DXT blocks to 2K and adds uniquely named unreferenced
sections as needed. It preserves nontexture sections and audits native bounds.
Use only a source DAT you are entitled to use, never an installed source as the
output. Generated DATs and local manifests are ignored by Git and not distributed.

## Launcher ownership tests

```powershell
$env:PYTHONPATH = 'tools'
python -m unittest discover -s tests -p 'test_*.py'
```

This tests process selection/refusal. It does not establish live game stability.
