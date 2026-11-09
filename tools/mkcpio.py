#!/usr/bin/env python3
"""Write an (empty) newc cpio archive, as the boot ramdisk for the shim.

An empty archive is just the trailer entry; ABL only needs a ramdisk blob to
exist so the shim can be handed one (and shim.c checks for a payload in it).
"""
import sys

FIELDS = 13


def entry(name, data=b"", ino=0, mode=0o100644):
    namez = name.encode() + b"\0"
    hdr = b"070701"
    vals = [ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(namez), 0]
    assert len(vals) == FIELDS
    hdr += b"".join(b"%08X" % v for v in vals)
    hdr += namez
    hdr += b"\0" * ((-len(hdr)) % 4)
    out = hdr + data
    out += b"\0" * ((-len(out)) % 4)
    return out


def main():
    out = sys.argv[1]
    blob = entry("TRAILER!!!", b"", ino=0)
    blob += b"\0" * ((-len(blob)) % 512)
    open(out, "wb").write(blob)
    print("mkcpio: %s  %d bytes (empty)" % (out, len(blob)))


if __name__ == "__main__":
    main()
