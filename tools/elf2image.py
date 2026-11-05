#!/usr/bin/env python3
"""ELF64 -> flat image laid out by virtual address.

`objcopy -O binary` places sections by file order; the shim is linked at 0 but
executes wherever ABL loaded it, so every byte must land at its p_vaddr
offset. This writer maps each PT_LOAD segment to p_vaddr, which is what
ABL copies (kernel_size bytes from the load address).

  elf2image.py shim.elf Image
"""
import struct
import sys

PT_LOAD = 1


def load_segments(elf):
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 1:
        sys.exit("error: not a little-endian ELF64 file")
    e_phoff = struct.unpack_from("<Q", elf, 32)[0]
    e_phentsize = struct.unpack_from("<H", elf, 54)[0]
    e_phnum = struct.unpack_from("<H", elf, 56)[0]
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags = struct.unpack_from("<II", elf, off)
        p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from(
            "<QQQQQ", elf, off + 8)
        if p_type != PT_LOAD or p_filesz == 0:
            continue
        if p_offset + p_filesz > len(elf):
            sys.exit("error: segment %d runs past end of file" % i)
        segs.append((p_vaddr, p_filesz, p_offset, p_memsz))
    if not segs:
        sys.exit("error: no PT_LOAD segments")
    return segs


def main():
    src, dst = sys.argv[1], sys.argv[2]
    elf = open(src, "rb").read()
    segs = load_segments(elf)
    end = max(v + f for v, f, _, _ in segs)
    mem = bytearray(end)
    prev = None
    for vaddr, filesz, offset, memsz in sorted(segs):
        if prev is not None and vaddr < prev:
            sys.exit("error: overlapping PT_LOAD segments (vaddr 0x%x < 0x%x)"
                     % (vaddr, prev))
        mem[vaddr:vaddr + filesz] = elf[offset:offset + filesz]
        prev = vaddr + memsz
    open(dst, "wb").write(mem)
    print("elf2image: %s -> %s  %d segments, image %d bytes, vaddr range "
          "0x%x..0x%x" % (src, dst, len(segs), len(mem),
                          min(v for v, *_ in segs), end))


if __name__ == "__main__":
    main()
