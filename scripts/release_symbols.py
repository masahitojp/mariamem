"""Inspect actual ELF/Mach-O sections and symbols; trimpath omits ldflags metadata."""
import struct
from pathlib import Path


def require_stripped(path):
    data = Path(path).read_bytes()
    def unpack(fmt, offset):
        try:
            return struct.unpack_from(fmt, data, offset)
        except struct.error as exc:
            raise ValueError('truncated release host') from exc
    if data[:6] == b'\x7fELF\x02\x01':
        offset, = unpack('<Q', 40)
        size, count, names = unpack('<HHH', 58)
        if size != 64 or not count or names >= count:
            raise ValueError('invalid ELF sections')
        sections = [unpack('<IIQQQQIIQQ', offset+i*size) for i in range(count)]
        strings = sections[names]
        table = data[strings[4]:strings[4]+strings[5]]
        for section in sections:
            name = table[section[0]:].split(b'\0', 1)[0]
            if section[1] == 2 or name.startswith((b'.debug_', b'.zdebug_')):
                raise ValueError('release host must omit symbols and DWARF (-s -w)')
    elif data[:4] == b'\xcf\xfa\xed\xfe':
        count, total = unpack('<II', 16)
        offset = 32
        for _ in range(count):
            command, size = unpack('<II', offset)
            if size < 8 or offset+size > 32+total:
                raise ValueError('invalid Mach-O commands')
            if command == 0x19:
                segment = unpack('<16s', offset+8)[0].rstrip(b'\0')
                if segment == b'__DWARF':
                    raise ValueError('release host must omit symbols and DWARF (-s -w)')
            if command == 2:
                symbols, nsyms, _, _ = unpack('<IIII', offset+8)
                for i in range(nsyms):
                    _, kind, _, _, _ = unpack('<IBBHQ', symbols+16*i)
                    # Undefined dynamic imports remain even with -s.
                    if kind & 0xe0 or kind & 0x0e:
                        raise ValueError('release host must omit symbols and DWARF (-s -w)')
            offset += size
    else:
        raise ValueError('unsupported release host format')
