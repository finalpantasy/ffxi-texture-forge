# FFXI Texture Forge

An experimental tool for testing one cause of black scenery and crashes when
Final Fantasy XI loads lots of large replacement textures: the game's own
limited space for keeping assets ready.

**The short version:** this alpha gives one exact version of FFXI a larger
internal asset pool while it runs. It does not turn FFXI into a modern game or
automatically make every texture mod work. It tests whether running out of
that particular space is the problem.

![Actual retail checkerboard texture test](docs/images/retail-checkerboard-test.png)

*This is a real retail screenshot from an earlier 2K checkerboard test. It is
not an 8K texture demo. The checkerboard makes it easy to see that a replacement
texture appeared in the game.*

## Why this might help

Imagine FFXI has a small shelf where it keeps the art it is using. A texture
mod can make the art take up more room. If the shelf fills, the game may fail
to load more assets. In some situations that can mean missing or black scenery,
or a crash.

This shelf is separate from your graphics card's memory. FFXI can run short of
its own asset space even when Windows still has memory available and the
graphics card still has room.

## What the alpha does

The public alpha checks that the game is the one exact build it was made for,
then enlarges FFXI's asset pool to about 1 GiB as the game starts. It changes
temporary memory in that running game process; it does not patch the installed
game DLLs or DAT files. The launcher starts and arms its own test client rather
than attaching to a game that is already running.

The repository also includes a small diagnostic addon and a tool for making an
artificial texture-pressure test DAT (an FFXI data file) from a local source
file. That test file is meant to measure the pool, not to provide attractive
replacement art.

## What the tests showed

On the supported retail build, using Large Address Aware (LAA) and dgVoodoo
configured to translate the game's Direct3D 8 graphics calls to Direct3D 11, a
short test loaded about 981 MiB into a pool of about 1 GiB. That left about 43
MiB free. The client completed a brief zone-out-and-back test without a black
screen or crash.

The stress DAT included extra, unreferenced texture sections. So this result
shows how much data the tested asset pool could hold; it does not mean that
981 MiB of new art was visible on screen or using that much graphics card
memory. These were short tests, not proof of long-term stability. An optional
addon/plugin comparison also crashed, and its cause is still unknown.

## A few terms, in everyday language

- **Asset pool:** FFXI's own shelf for loaded game assets. Making this larger is
  what the public alpha tests.
- **LAA (Large Address Aware):** a marker on a 32-bit program that lets it use
  more of the memory locations Windows makes available on 64-bit Windows. It
  does not enlarge FFXI's asset pool by itself.
- **dgVoodoo:** a compatibility wrapper that acts like a graphics translator.
  In the supported retail setup, it translates FFXI's older Direct3D 8 requests
  into Direct3D 11 requests. It does not add asset-pool space.
- **VRAM:** memory on the graphics card. It is another separate limit; having
  free VRAM does not guarantee that FFXI's own asset pool has room.

The retail adapter described here has been tested with the Direct3D 11 setup.
It does not convert FFXI itself to Direct3D 11 or Direct3D 12.

## What this release does not do

This alpha does **not** include a system for replacing textures outside FFXI's
asset pool. It does not stream high-resolution textures, unload them from a
renderer cache, replace models, or add modern lighting. It is a memory-pool
experiment, not a ready-to-use high-resolution mod manager or a guaranteed fix
for every black screen.

Separately, a private offline prototype explored keeping replacement textures
outside the game's usual asset pool. A narrow Direct3D 11 test and a
Direct3D 12-configured area-transition test produced promising results, but
that prototype and its test tools are not included here. The Direct3D 12 route
still needs more verification, and neither test establishes support for retail
Windower or every texture mod. See the [experiment results](docs/renderer-experiment-results.md)
and [remaining work](docs/renderer-roadmap.md).

## Try the alpha

This is experimental source for a local test setup. Use a separate copy of
Windower and FFXI, and check that your client matches the
[supported build](docs/supported-build.json) before building. The
[build and test guide](docs/build.md) lists the required tools and setup steps.
The project does not include FFXI, Windower, dgVoodoo, XIPivot, game DATs, or
other third-party mod assets. See the [third-party notices](NOTICE.md).

Get the [v0.1.0-alpha.1 release](https://github.com/finalpantasy/ffxi-texture-forge/releases/tag/v0.1.0-alpha.1).

MIT licensed. Final Fantasy XI and its game content belong to Square Enix. This
project is not affiliated with Square Enix or Windower.
