"""Generate bounded native loader pressure from a user-supplied local DAT."""
import argparse,ctypes,hashlib,math,os,struct,time
from pathlib import Path
from dat_format import inspect_dat
import numpy as np
SIZE_MASK = 0x7ffff << 7
MAX_SECTION = 0x7ffff * 16
PAYLOAD_TIERS = (0,512,768,896,960)
class Helpers:
    @staticmethod
    def sha(path):
        digest=hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
        return digest.hexdigest()
lab=Helpers()
def sections(data):
    pos = 0
    while pos + 16 <= len(data):
        meta = struct.unpack_from('<I', data, pos + 4)[0]
        size = ((meta >> 7) & 0x7ffff) * 16
        if not size:
            if any(data[pos:]):
                raise ValueError('Nonzero data after DAT terminator')
            break
        if size < 16 or pos + size > len(data):
            raise ValueError('Invalid native section bounds')
        yield pos, meta, memoryview(data)[pos:pos + size]
        pos += size
    if any(data[pos:]):
        raise ValueError('Unparsed nonzero DAT trailer')

def enlarge(section, dimension):
    if dimension not in (1024, 2048):
        raise ValueError('Stress dimensions must remain inside verified native section limits')
    meta = struct.unpack_from('<I', section, 4)[0]
    if meta & 0x7f != 0x20 or len(section) < 85 or section[16] != 0xa1:
        return bytes(section), None
    width, height = struct.unpack_from('<II', section, 37)
    fmt = bytes(section[73:77])
    if fmt not in (b'1TXD', b'3TXD') or width < 4 or height < 4 or width % 4 or height % 4:
        return bytes(section), None
    block = 8 if fmt == b'1TXD' else 16
    payload = width // 4 * (height // 4) * block
    stated, pitch = struct.unpack_from('<II', section, 77)
    tail = section[85 + payload:]
    if stated != payload or pitch != width // 4 * block or len(tail) > 15 or any(tail):
        return bytes(section), None
    # Never downsize an existing dimension. Rectangular source UV content may
    # look stretched; this fixture intentionally prioritizes valid pressure.
    neww, newh = max(dimension, width), max(dimension, height)
    size = neww // 4 * (newh // 4) * block
    if 85 + size + 15 > MAX_SECTION:
        raise ValueError('Would cross the native per-section ceiling')
    blocks = np.frombuffer(section[85:85 + payload], dtype='V' + str(block)).reshape(height // 4, width // 4)
    x = np.arange(neww // 4, dtype=np.int64) * (width // 4) // (neww // 4)
    y = np.arange(newh // 4, dtype=np.int64) * (height // 4) // (newh // 4)
    raw = blocks[y[:, None], x[None, :]].tobytes()
    out = bytearray(section[:85])
    struct.pack_into('<II', out, 37, neww, newh)
    struct.pack_into('<II', out, 77, len(raw), neww // 4 * block)
    out.extend(raw); out.extend(b'\0' * (-len(out) % 16))
    struct.pack_into('<I', out, 4, (meta & ~SIZE_MASK) | (len(out) // 16 << 7))
    return bytes(out), {'name_hex': bytes(section[17:33]).hex(), 'before': [width, height],
                        'after': [neww, newh], 'format': fmt.decode(), 'payload_bytes': len(raw)}

def audit_file(path):
    """Stream header audit: avoid mapping a multi-GiB fixture into Python RAM."""
    size = path.stat().st_size
    pos, textures, payload = 0, 0, 0
    names, preserved = set(), []
    with path.open('rb') as stream:
        while pos + 16 <= size:
            stream.seek(pos); header = stream.read(85)
            meta = struct.unpack_from('<I', header, 4)[0]
            length = ((meta >> 7) & 0x7ffff) * 16
            if not length:
                stream.seek(pos)
                if any(stream.read()):
                    raise ValueError('Nonzero fixture trailer')
                pos = size; break
            if length < 16 or pos + length > size:
                raise ValueError('Fixture section bounds invalid')
            if meta & 0x7f == 0x20:
                textures += 1
                if len(header) >= 85 and header[16] == 0xa1 and header[73:77] in (b'1TXD', b'3TXD'):
                    w, h = struct.unpack_from('<II', header, 37)
                    block = 8 if header[73:77] == b'1TXD' else 16
                    if w < 4 or h < 4 or w % 4 or h % 4:
                        raise ValueError('Invalid inflated texture dimensions')
                    expected = w // 4 * (h // 4) * block
                    stated, pitch = struct.unpack_from('<II', header, 77)
                    if stated != expected or pitch != w // 4 * block or not 0 <= length - 85 - expected <= 15:
                        raise ValueError('Invalid inflated DXT payload/header')
                    name = header[17:33]
                    if name.startswith(b'ovr') and name in names:
                        raise ValueError('Duplicate generated pressure texture ID')
                    names.add(name); payload += expected
            else:
                stream.seek(pos)
                preserved.append(hashlib.sha256(stream.read(length)).hexdigest())
            pos += length
        if pos < size:
            stream.seek(pos)
            if any(stream.read()):
                raise ValueError('Unparsed fixture bytes')
    return {'bytes': size, 'texture_sections': textures, 'compressed_payload_bytes': payload,
            'nontexture_sha256': preserved, 'sha256': lab.sha(path)}

def write_fixture(data, path, dimension, minimum_payload_mib, deadline):
    original = inspect_dat(data)
    if original['problems']:
        raise ValueError('Seed DAT audit failed')
    if minimum_payload_mib not in PAYLOAD_TIERS:
        raise ValueError('Choose a bounded loader-pressure tier')
    plan, preserved, inflated, template, existing_names = [], [], [], None, set()
    base_payload = original['base_dxt_bytes']
    # Keep only compact replacements in the plan; write/resize one section at
    # a time later, keeping host memory independent of output DAT size.
    for offset, meta, section in sections(data):
        if time.monotonic() > deadline:
            raise TimeoutError('Fixture build deadline')
        if meta & 0x7f == 0x20:
            existing_names.add(bytes(section[17:33]))
        else:
            preserved.append(hashlib.sha256(section).hexdigest())
        enlarged, info = enlarge(section, dimension)
        if info:
            old = next(t for t in original['textures'] if t['offset'] == offset)
            base_payload += info['payload_bytes'] - old['base_dxt_bytes']
            inflated.append(info)
            if template is None and info['format'] == '3TXD':
                template = enlarged
        plan.append((offset, len(section), bool(info)))
    if not inflated or template is None:
        raise ValueError('No verified DXT3 section available for this pressure fixture')
    per_extra = struct.unpack_from('<I', template, 77)[0]
    extra = max(0, math.ceil((minimum_payload_mib * 1024**2 - base_payload) / per_extra))
    if extra > 1024:
        raise ValueError('Too many generated texture sections')
    first_texture = next(offset for offset, meta, _ in sections(data) if meta & 0x7f == 0x20)
    with path.open('xb') as out:
        for offset, length, changed in plan:
            if time.monotonic() > deadline:
                raise TimeoutError('Fixture build deadline')
            if offset == first_texture:
                # Valid extra sections go inside the existing texture group.
                # They are NOT referenced by geometry: classify this as loader
                # pressure, never as proof all payload was drawn/resident.
                for index in range(extra):
                    name = (f'ovr{index:012x}').encode('ascii').ljust(16, b'\0')
                    if name in existing_names:
                        raise ValueError('Generated texture ID collides with seed')
                    appended = bytearray(template); appended[17:33] = name; out.write(appended)
            section = memoryview(data)[offset:offset + length]
            out.write(enlarge(section, dimension)[0] if changed else section)
        consumed = sum(length for _, length, _ in plan)
        out.write(data[consumed:])
    after = audit_file(path)
    if after['nontexture_sha256'] != preserved:
        raise ValueError('Nontexture/geometry bytes changed')
    return {'before_bytes': len(data), 'seed_sha256': original['sha256'], 'dimension_floor': dimension,
            'inflated_sections': len(inflated), 'extra_unreferenced_texture_sections': extra,
            'stress_kind': 'loader_and_referenced_textures' if extra else 'referenced_textures',
            'nontexture_sections_identical': True, **after}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--payload-mib',type=int,choices=PAYLOAD_TIERS,default=768)
    args=parser.parse_args()
    if os.name=='nt':ctypes.WinDLL('kernel32').SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    if args.source.resolve()==args.output.resolve():raise ValueError('Use a separate output file')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    result=write_fixture(args.source.read_bytes(),args.output,2048,args.payload_mib,time.monotonic()+540)
    import json
    with args.output.with_suffix('.manifest.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({key:result[key] for key in ['bytes','compressed_payload_bytes','extra_unreferenced_texture_sections','sha256']},indent=2))
