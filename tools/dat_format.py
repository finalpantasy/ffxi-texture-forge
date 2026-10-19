"""Read-only native DAT header inspection."""
import collections,hashlib,struct

def inspect_dat(data):
    pos = 0
    textures = []
    sections = collections.Counter()
    problems = []
    while pos + 16 <= len(data):
        meta = struct.unpack_from('<I', data, pos + 4)[0]
        # Retail walker masks 19 size bits; bit 26 is a flag, not size.
        kind, size = meta & 0x7f, ((meta >> 7) & 0x7ffff) * 16
        if not size:
            if any(data[pos:]):
                problems.append({'offset': pos, 'error': 'zero-length section before nonzero trailing data'})
            break
        if size < 16 or pos + size > len(data):
            problems.append({'offset': pos, 'error': 'section out of file bounds', 'size': size})
            break
        sections[hex(kind)] += 1
        if kind == 0x20:
            start = pos + 16
            if size < 16 + 57:
                problems.append({'offset': pos, 'error': 'short texture header'})
            else:
                texture_type = data[start]
                name = data[start+1:start+17].decode('ascii', 'replace').rstrip('\0 ')
                width, height = struct.unpack_from('<II', data, start+21)
                bit_count = struct.unpack_from('<H', data, start+31)[0]
                valid = width > 0 and height > 0 and width <= 16384 and height <= 16384
                fmt = data[start+57:start+61].decode('ascii', 'replace') if texture_type == 0xa1 and size >= 85 else None
                payload = None
                if valid and fmt in ('1TXD', '3TXD', '5TXD'):
                    payload = max(1,(width+3)//4) * max(1,(height+3)//4) * (8 if fmt == '1TXD' else 16)
                    if start+69+payload > pos+size:
                        problems.append({'offset': pos, 'error': 'texture payload truncated', 'name': name})
                if not valid:
                    problems.append({'offset': pos, 'error': 'invalid texture dimensions', 'name': name, 'dimensions': [width,height]})
                textures.append({'name': name, 'width': width, 'height': height,
                                 'type': hex(texture_type), 'format': fmt,
                                 'bit_count': bit_count, 'section_bytes': size,
                                 'base_dxt_bytes': payload,
                                 'rgba_equivalent_bytes': width*height*4 if valid else None,
                                 'offset': pos})
        pos += size
    return {'dat_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'sections': dict(sections), 'textures': textures, 'problems': problems,
            'base_dxt_bytes': sum(t['base_dxt_bytes'] or 0 for t in textures),
            'rgba_equivalent_bytes': sum(t['rgba_equivalent_bytes'] or 0 for t in textures),
            'largest_dimension': max((max(t['width'],t['height']) for t in textures),default=0),
            'has_zone_geometry': bool(sections['0x1c'] or sections['0x2e'])}
