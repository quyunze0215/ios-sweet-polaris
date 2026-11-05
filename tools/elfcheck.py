#!/usr/bin/env python3
"""Checks used by shim/build.sh: relocations, symbols, image sanity.

  elfcheck.py abs64  OBJ...        # no absolute (ABS64/ABS32) relocations in C objects
  elfcheck.py relocs ELF           # linked ELF carries no relocation sections
  elfcheck.py symbol ELF NAME      # print st_value of NAME
  elfcheck.py image  FILE          # flat image sanity (size, not empty)
"""
import struct
import sys

SHT_RELA = 4
SHT_REL = 9
SHT_SYMTAB = 2
R_AARCH64_ABS64 = 257
R_AARCH64_ABS32 = 258


def ehdr(elf):
    if elf[:4] != b"\x7fELF" or elf[4] != 2:
        sys.exit("error: not an ELF64 file")
    return dict(
        e_shoff=struct.unpack_from("<Q", elf, 40)[0],
        e_shentsize=struct.unpack_from("<H", elf, 58)[0],
        e_shnum=struct.unpack_from("<H", elf, 60)[0],
        e_shstrndx=struct.unpack_from("<H", elf, 62)[0],
    )


def sections(elf):
    h = ehdr(elf)
    out = []
    for i in range(h["e_shnum"]):
        off = h["e_shoff"] + i * h["e_shentsize"]
        name, sh_type = struct.unpack_from("<II", elf, off)
        sh_offset, sh_size, sh_link = struct.unpack_from("<QQI", elf, off + 24)
        sh_entsize = struct.unpack_from("<Q", elf, off + 56)[0]
        out.append(dict(name=name, type=sh_type, offset=sh_offset, size=sh_size,
                        link=sh_link, entsize=sh_entsize))
    return h, out


def strtab(elf, h, secs, idx):
    s = secs[idx]
    return elf[s["offset"]:s["offset"] + s["size"]]


def cmd_abs64(paths):
    bad = 0
    for path in paths:
        elf = open(path, "rb").read()
        _, secs = sections(elf)
        for s in secs:
            if s["type"] not in (SHT_RELA, SHT_REL) or s["entsize"] == 0:
                continue
            n = s["size"] // s["entsize"]
            for i in range(n):
                off = s["offset"] + i * s["entsize"]
                r_info = struct.unpack_from("<Q", elf, off + 8)[0]
                rtype = r_info & 0xFFFFFFFF
                if rtype in (R_AARCH64_ABS64, R_AARCH64_ABS32) and s["type"] == SHT_RELA:
                    print("error: %s: absolute relocation type %d" % (path, rtype))
                    bad += 1
    if bad:
        sys.exit(1)
    print("elfcheck: abs64 ok (%d object(s))" % len(paths))


def cmd_relocs(path):
    elf = open(path, "rb").read()
    _, secs = sections(elf)
    left = [s for s in secs if s["type"] in (SHT_RELA, SHT_REL)]
    if left:
        sys.exit("error: %s still has %d relocation section(s)" % (path, len(left)))
    print("elfcheck: relocs ok (none left in %s)" % path)


def cmd_symbol(path, name):
    elf = open(path, "rb").read()
    h, secs = sections(elf)
    want = name.encode()
    for s in secs:
        if s["type"] != SHT_SYMTAB or s["entsize"] == 0:
            continue
        strings = strtab(elf, h, secs, s["link"])
        for i in range(s["size"] // s["entsize"]):
            off = s["offset"] + i * s["entsize"]
            st_name, st_info, st_other, st_shndx = struct.unpack_from("<IBBH", elf, off)
            st_value, st_size = struct.unpack_from("<QQ", elf, off + 8)
            end = strings.find(b"\0", st_name)
            if strings[st_name:end] == want:
                print(st_value)
                return
    sys.exit("error: symbol %s not found in %s" % (name, path))


def cmd_image(path):
    data = open(path, "rb").read()
    if len(data) < 64:
        sys.exit("error: %s is only %d bytes" % (path, len(data)))
    head = data[:16]
    if head == b"\0" * 16:
        sys.exit("error: %s starts with zeros (wrong link address?)" % path)
    print("elfcheck: image ok (%d bytes, head %s)" % (len(data), head.hex()))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "abs64":
        cmd_abs64(rest)
    elif cmd == "relocs":
        cmd_relocs(rest[0])
    elif cmd == "symbol":
        cmd_symbol(rest[0], rest[1])
    elif cmd == "image":
        cmd_image(rest[0])
    else:
        sys.exit("error: unknown command %s" % cmd)


if __name__ == "__main__":
    main()
