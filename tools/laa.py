"""Inspect/set x86 EXE LAA with a verified backup and a one-byte audit.

No third-party patcher is run. Inspect is the default; --apply is explicit.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
from datetime import datetime, timezone


def identity(data):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Not a DOS/PE executable')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if pe + 26 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Invalid PE header')
    machine, = struct.unpack_from('<H', data, pe + 4)
    flags, = struct.unpack_from('<H', data, pe + 22)
    magic, = struct.unpack_from('<H', data, pe + 24)
    if machine != 0x14c or magic != 0x10b or not flags & 2 or flags & 0x2000:
        raise ValueError('Expected a native x86 PE32 EXE, not a DLL')
    return {'machine': 'x86', 'characteristics_offset': pe + 22,
            'characteristics': flags, 'large_address_aware': bool(flags & 0x20),
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def candidate(data):
    info = identity(data)
    result = bytearray(data)
    struct.pack_into('<H', result, info['characteristics_offset'],
                     info['characteristics'] | 0x20)
    return bytes(result)


def exclusive_file(path):
    if os.name != 'nt':
        raise OSError('Apply is Windows-only')
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0xc0000000, 0, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    return os.fdopen(fd, 'r+b')


def apply(path, evidence):
    path = path.resolve(strict=True)
    if path.suffix.lower() != '.exe':
        raise ValueError('Only .exe targets are allowed')
    # Exclusive Windows handle fails if the EXE is loaded or another writer owns it.
    with exclusive_file(path) as handle:
        original = handle.read()
        before = identity(original)
        if before['large_address_aware']:
            return {'status': 'already_enabled', 'path': str(path), 'identity': before}
        updated = candidate(original)
        differences = [i for i, (a, b) in enumerate(zip(original, updated)) if a != b]
        if differences != [before['characteristics_offset']]:
            raise AssertionError('Patch would change more than the LAA byte')
        evidence.mkdir(parents=True, exist_ok=False)
        backup = evidence / (path.name + '.original')
        with backup.open('xb') as out:
            out.write(original)
            out.flush()
            os.fsync(out.fileno())
        if backup.read_bytes() != original:
            raise OSError('Backup verification failed; target has not been changed')
        journal = {'status': 'backup_verified', 'path': str(path),
                   'backup': str(backup.resolve()), 'before': before,
                   'planned_sha256': hashlib.sha256(updated).hexdigest(),
                   'changed_offsets': differences,
                   'timestamp_utc': datetime.now(timezone.utc).isoformat()}
        receipt = evidence / 'receipt.json'
        receipt.write_text(json.dumps(journal, indent=2), encoding='utf-8')
        handle.seek(before['characteristics_offset'])
        handle.write(updated[before['characteristics_offset']:before['characteristics_offset'] + 1])
        handle.flush()
        os.fsync(handle.fileno())
        handle.seek(0)
        actual = handle.read()
        if actual != updated:
            # Preserve failed state and receipt; do not silently perform a rollback.
            raise OSError('Readback mismatch; preserve evidence and inspect before further writes')
        journal.update(status='enabled_verified', after=identity(actual),
                       all_other_bytes_identical=True)
        receipt.write_text(json.dumps(journal, indent=2), encoding='utf-8')
    if path.read_bytes() != updated:
        raise OSError('Post-close readback mismatch')
    return journal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    if args.apply:
        if args.evidence is None:
            parser.error('--apply requires a new --evidence directory')
        result = apply(args.exe, args.evidence)
    else:
        result = {'path': str(args.exe.resolve()), 'identity': identity(args.exe.read_bytes())}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
