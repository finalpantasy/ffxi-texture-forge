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
offline Ashita/DX11 test. Retail Windower, crowded combat, broad asset matching,
further repeated zoning and long-session behavior remain unqualified.

## D3D12-configured route follow-up

A separate owned offline x86 Ashita run used dgVoodoo 2.87.5 configured for
D3D12 FL12.0, Large Address Aware, 100 distinct external 8K DDS replacements
(6.375 GiB of aggregate full-mip source payload), a 512 MiB resident budget and
a 192 MiB staging budget. It completed 25 real area transitions in 378.82
seconds. Fifty-five of the 100 manifest entries were observed uploading and
drawing. Peak stream-owned resident payload was 469.33 MiB and peak staging was
170.67 MiB; the route recorded 224,480 replacement draws and zero stream
failures, hook conflicts or budget rejects. The final capture showed a rendered
scene without a black-world capture. It did not show all 100 replacements on
screen at once.

The run requested D3D12 FL12.0 and loaded `d3d12.dll`, but its receipt leaves a
native device/GPU trace pending. Across 7,735 sampled frames, p95 was 56.05 ms,
p99 was 139.47 ms and the maximum was 600.81 ms; this is not a matched
performance comparison and does not establish performance readiness.

A controlled six-entity local scene also completed its scripted actions and
cleanup. The later four-minute soak did not complete: the owned offline map
server's inactivity watchdog killed its map process after a main tick exceeded
2,000 ms, and the supervisor then terminated the client. The final stream
samples had no texture failures or budget overflow, and no GPU-reset or
application-crash event was found. This is a test-environment interruption,
not evidence of an FFXI renderer crash; long-session client stability remains
unknown. A separate combined run also reached the stream addon's 510-second
safety lifetime before completing its soak.

## Public release boundary

This repository publishes the measurements and limitations only. The local
prototype, stress harness, diagnostic texture pack, wrapper binaries and raw
runtime captures are not included. The existing retail asset-pool adapter is a
separate approach: it increases the native arena and does not implement the
renderer-side substitution described here. The offline D3D12 route is a narrow
test result, not retail Windower or general-purpose DX12 support.
