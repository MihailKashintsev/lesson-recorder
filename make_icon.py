import struct, zlib, os
if os.path.exists("app_icon.png"):
    raise SystemExit(0)
def chunk(t, d):
    c = zlib.crc32(t + d) & 0xffffffff
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", c)
sig  = b"\x89PNG\r\n\x1a\n"
ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
idat = chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
iend = chunk(b"IEND", b"")
open("app_icon.png", "wb").write(sig + ihdr + idat + iend)
print("created app_icon.png")
