# Renderer-side high-resolution replacement

The verified adapter enlarges the game's native asset pool. A separate local
Ashita/DX11 experiment has demonstrated keeping the native assets in that pool
while substituting high-resolution resources through an external replacement
path. That prototype is **not included in this public release**; retail
Windower and DX12 support have not been qualified.

## Current evidence (October 19, 2026)

The offline x86 client ran with dgVoodoo's DX11 renderer. The test allocated 100
distinct diagnostic BC2/DXT3 textures, up to 16,384 pixels on the long edge,
with 25.50 GiB of aggregate full-mip texture payload. All 100 resources passed
three synchronized readback rounds with no allocation or readback failures.
After the cache budget was reduced to 8 GiB and resources were evicted, one
Reisenjima scene rendered with nine cached replacements (2.167 GiB), 22,496
replacement draws and zero resource failures. There was no black screen or
client crash in this test.

These are allocation/accounting bytes, not proof that 25.50 GiB was resident in
physical VRAM. The pressure run sampled up to 22,200 MiB of physical GPU usage
while unrelated GPU work was active, so those readings cannot be attributed to
this test. The client did not exhaust sampled GPU free memory. This demonstrates
one experimental replacement path, not a universal limit or a fix for every
crowded-area blackout. See the [experiment record](renderer-experiment-results.md)
for measurements and boundaries.

## Remaining work

1. Repeat the bounded upload, draw and readback qualification for DX12. The
   local test reached 16K on the DX11 path; that is not proof of DX12 or broad
   FFXI compatibility.
2. Trace texture creation, uploads, identity and lifetime in an owned offline
   client. The prototype matches a narrow diagnostic texture; a stable general
   replacement identity, duplicate-data handling and late uploads remain open.
3. Verify replacement behavior across real assets, preserving dimensions as
   seen by the game, UV interpretation, alpha, filtering and animation. One
   diagnostic texture and one recovered scene are not broad asset compatibility.
4. Measure separate GPU and CPU staging budgets. Measured staging peaked at
   682.67 MiB against a configured 768 MiB cap in this test. Continue measuring
   actual process and driver behavior; never assume all GPU allocations are
   outside 32-bit virtual address space.
5. Qualify safe eviction, reload, zoning and device reset/loss handling over
   repeated routes and longer sessions. The prototype exercised resource
   clearing and reset, but repeated eviction, zone cycling and long-session
   behavior remain unqualified. Preserve fallback to the original texture.

Acceptance still requires real high-resolution pixels reaching draws, bounded
steady-state and peak CPU/GPU storage, repeated unload/reload, reset recovery,
and unchanged unmatched textures. A large source image or a mock cache alone is
not a pass.
