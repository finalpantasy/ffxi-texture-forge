# Next milestone: renderer-side high-resolution replacement

The verified adapter only enlarges an engine pool. This milestone will
investigate keeping small native textures while substituting larger graphics
resources outside that pool. It is not available in the current release.

1. Prove an actual 8192×8192 texture can be uploaded, drawn and read back through
   the existing D3D8 → dgVoodoo DX11 path in a bounded synthetic process. Repeat
   for DX12 separately. An API pass is not an FFXI compatibility pass.
2. Trace one texture's creation, uploads, identity and lifetime in an owned
   offline client. Determine whether texture bytes, resource descriptions and
   call context supply a stable replacement identity. Handle duplicate data and
   late uploads without confusing unrelated surfaces.
3. Replace one qualified surface while preserving dimensions as seen by the
   game, UV interpretation, alpha, filtering and animation behavior. Capture
   original/replaced evidence under matched conditions.
4. Add a GPU budget and a separately bounded CPU staging budget. Free staging
   data after upload; measure actual process/driver behavior. A default-pool
   resource is a hypothesis to test, not a guarantee that a wrapper keeps no
   CPU copy. Never assume all GPU allocations are outside 32-bit VA.
5. Add safe eviction, reload, zoning and device reset/loss handling. Release
   resources only when no draw still depends on them. Keep graphics API work on
   the device's correct thread and make missing replacements fall back to the
   original texture.

Acceptance requires real 8K pixels reaching a draw, bounded steady-state and
peak CPU/GPU storage, repeated unload/reload, reset recovery and unchanged
unmatched textures. A large source image or a mock cache alone is not a pass.
