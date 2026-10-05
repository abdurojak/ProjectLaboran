import struct
import zlib
from datetime import datetime
from io import BytesIO


RAR4_MARKER = b'Rar!\x1a\x07\x00'


def _header(payload):
    return struct.pack('<H', zlib.crc32(payload) & 0xFFFF) + payload


def _dos_time(value):
    value = value or datetime.now()
    year = min(max(value.year, 1980), 2107)
    return (
        ((year - 1980) << 25)
        | (value.month << 21)
        | (value.day << 16)
        | (value.hour << 11)
        | (value.minute << 5)
        | (value.second // 2)
    )


def build_rar4(files):
    """Build a standards-compliant, uncompressed RAR 4 archive in memory.

    ``files`` is an iterable of ``(archive_name, bytes, modified_at)`` tuples.
    Storing instead of compressing keeps evidence files (PDF/JPEG/PNG) intact
    and avoids an external proprietary RAR executable.
    """
    output = BytesIO()
    output.write(RAR4_MARKER)
    output.write(_header(struct.pack('<BHHHI', 0x73, 0, 13, 0, 0)))

    for archive_name, content, modified_at in files:
        name = archive_name.replace('\\', '/').encode('utf-8')
        content = bytes(content)
        header_size = 32 + len(name)
        payload = struct.pack(
            '<BHHIIBIIBBHI',
            0x74,       # file header
            0x8000,     # long block; PACK_SIZE is the additional data size
            header_size,
            len(content),
            len(content),
            3,          # Unix host OS
            zlib.crc32(content) & 0xFFFFFFFF,
            _dos_time(modified_at),
            20,         # RAR 2.0 extraction compatibility
            0x30,       # store (no compression)
            len(name),
            0o100644,
        ) + name
        output.write(_header(payload))
        output.write(content)

    output.write(_header(struct.pack('<BHH', 0x7B, 0x4000, 7)))
    return output.getvalue()
