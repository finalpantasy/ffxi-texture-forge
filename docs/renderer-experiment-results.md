# Renderer-side replacement experiment

**Status:** local prototype result; not part of the public runtime.
**Date:** October 19, 2026.

## Result

An owned offline x86 FFXI client running under Ashita and dgVoodoo's DX11
renderer completed a controlled high-resolution texture test without a black
screen or client crash. A local D3D8 replacement prototype allocated 100
distinct diagnostic BC2/DXT3 textures, with dimensions up to 16,384 pixels on
the long edge. Their full-mip payload totaled 27,380,419,680 bytes (25.50 GiB).
Each resource passed three synchronized readback rounds: 300 resource draws and
900 sampled RGB pixels, with no resource failures.

The capacity run used a 32 GiB configured replacement-cache budget and a
768 MiB staging cap; measured peak staging was 682.67 MiB. Sampled physical GPU
usage peaked at 22,200 MiB, with 1,939 MiB free at the lowest sample. Other GPU
work was active, so these readings include unrelated allocations. The test did
not exhaust the sampled physical free-memory counter and does not establish
simultaneous physical residency of the 25.50 GiB accounting total.

After the cache budget was reduced to 8 GiB and resources were evicted, the
client entered one Reisenjima scene. That checkpoint had nine cached
replacement resources totaling 2.167 GiB, 22,496 replacement draws, zero
resource failures, 560.71 MiB of client private memory, and 3,036.62 MiB of free
process address space. The unchanged native asset arena was 192 MiB, with
21.76 MiB used. A native capture showed terrain, vegetation, an NPC and the
player rendering with obvious diagnostic replacement pixels. One recovered
scene does not establish long-session smoothness: its median sampled frame
interval matched baseline, while recovery p99 reached 259.06 ms.

## What this says about the fix

The useful mechanism is to keep the game's ordinary native textures in its
asset pool and substitute selected high-resolution resources in the renderer's
external replacement path. A budget and explicit resource clearing keep the
experimental HD resources separate from the native asset-pool allocation. In
an earlier controlled A/B, identical 220 MiB compressed pixels in native DAT
replacements crashed in the stock asset arena with about 2.97 GiB of process
address space still free; the external path rendered those pixels and passed
two leave/return cycles. This supports the native asset pool as a real
bottleneck for that workload, rather than proving GPU memory was the cause.

The 16K result is not a discovered maximum: the tested workload passed, and no
failure threshold was reached. It does not show that all 100 textures were
visible at once, that all 25.50 GiB were resident in VRAM, or that this path
fixes the original crowded-area blackout in every environment. It was an
offline Ashita/DX11 test. Retail Windower, DX12 with this workload, crowded
combat, broad asset matching, repeated zoning and long-session behavior remain
unqualified.

## Public release boundary

This repository publishes the measurements and limitations only. The local
prototype, stress harness, diagnostic texture pack, wrapper binaries and raw
runtime captures are not included. The existing retail asset-pool adapter is a
separate approach: it increases the native arena and does not implement the
renderer-side substitution described here.
