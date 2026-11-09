#!/usr/bin/env python3
"""Minimal Android boot image header v0-v2 packer.

Reimplemented for the ios-sweet tree because the upstream build script expects
tools/mkbootimg.py but only the AOSP binary was historically used. Layout and
field offsets follow AOSP's bootimg.h; verified by round-tripping through
tools/unpack_bootv2.py.

  mkbootimg.py -o out.img --kernel K --ramdisk R [--dtb D] --header_version 1
      --pagesize 4096 --base 0 --kernel_offset 0x8000 ...
      --os_version 0x200001a2 --cmdline "..."
"""
import argparse
import hashlib
import struct
import sys

MAGIC = b"ANDROID!"
HDR_V0 = 1632
HDR_V1 = 1648
HDR_V2 = 1660


def pad(data, page):
    return data + b"\0" * ((-len(data)) % page)


def parse_os_version(text):
    if not text:
        return 0
    if text.startswith(("0x", "0X")):
        return int(text, 16) & 0xFFFFFFFF
    if text.isdigit():
        return int(text) & 0xFFFFFFFF
    parts = [int(x) for x in text.split(".")]
    while len(parts) < 3:
        parts.append(0)
    a, b, c = parts[:3]
    return ((a << 25) | (b << 18) | (c << 11)) & 0xFFFFFFFF


def parse_patch_level(text):
    if not text:
        return 0
    y, m = text.split("-")
    return (((int(y) - 2000) << 4) | int(m)) & 0x7FF


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--kernel", required=True)
    p.add_argument("--ramdisk")
    p.add_argument("--second")
    p.add_argument("--dtb")
    p.add_argument("--header_version", type=int, default=0)
    p.add_argument("--pagesize", type=int, default=2048)
    p.add_argument("--base", type=lambda x: int(x, 0), default=0)
    p.add_argument("--kernel_offset", type=lambda x: int(x, 0), default=0)
    p.add_argument("--ramdisk_offset", type=lambda x: int(x, 0), default=0)
    p.add_argument("--second_offset", type=lambda x: int(x, 0), default=0)
    p.add_argument("--tags_offset", type=lambda x: int(x, 0), default=0)
    p.add_argument("--dtb_offset", type=lambda x: int(x, 0), default=0)
    p.add_argument("--os_version", default="0")
    p.add_argument("--os_patch_level")
    p.add_argument("--cmdline", default="")
    p.add_argument("--board", default="")
    a = p.parse_args()

    if a.header_version not in (0, 1, 2):
        sys.exit("error: only header versions 0, 1 and 2 are supported")

    kernel = open(a.kernel, "rb").read()
    ramdisk = open(a.ramdisk, "rb").read() if a.ramdisk else b""
    second = open(a.second, "rb").read() if a.second else b""
    dtb = open(a.dtb, "rb").read() if a.dtb else b""

    addr = lambda off: (a.base + off) & 0xFFFFFFFF
    cmdline = a.cmdline.encode()[:511] + b"\0"
    name = a.board.encode()[:15] + b"\0"
    os_version = parse_os_version(a.os_version)
    os_version |= parse_patch_level(a.os_patch_level)

    # Legacy id[] = SHA1 over each payload and its size (as AOSP does).
    sha = hashlib.sha1()
    for blob in (kernel, ramdisk, second):
        sha.update(blob)
        sha.update(struct.pack("<I", len(blob)))
    img_id = sha.digest() + b"\0" * 12

    hdr = MAGIC
    hdr += struct.pack(
        "<10I",
        len(kernel), addr(a.kernel_offset),
        len(ramdisk), addr(a.ramdisk_offset),
        len(second), addr(a.second_offset),
        addr(a.tags_offset), a.pagesize,
        a.header_version, os_version,
    )
    hdr += name.ljust(16, b"\0")
    hdr += cmdline.ljust(512, b"\0")
    hdr += img_id
    hdr += b"\0" * 1024  # extra_cmdline
    assert len(hdr) == HDR_V0, len(hdr)

    if a.header_version >= 1:
        hdr += struct.pack("<IQI", 0, 0, HDR_V1)
    if a.header_version >= 2:
        hdr += struct.pack("<IQ", len(dtb), addr(a.dtb_offset))

    out = pad(hdr, a.pagesize)
    out += pad(kernel, a.pagesize)
    out += pad(ramdisk, a.pagesize)
    out += pad(second, a.pagesize)
    if a.header_version >= 1:
        out += pad(b"", a.pagesize)  # recovery_dtbo (none)
    if a.header_version >= 2:
        out += pad(dtb, a.pagesize)

    with open(a.output, "wb") as f:
        f.write(out)
    print("mkbootimg: %s  header v%d  page %d  kernel %d  ramdisk %d%s%s  total %d"
          % (a.output, a.header_version, a.pagesize, len(kernel), len(ramdisk),
             "  dtb %d" % len(dtb) if dtb else "",
             "  os_version 0x%08x" % os_version, len(out)))


if __name__ == "__main__":
    main()
