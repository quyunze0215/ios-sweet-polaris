#!/usr/bin/env python3
"""Extract the stock Qualcomm device trees from a Mix 2S (polaris) boot image.

polaris' ABL picks one of the DTBs appended after the gzip-compressed kernel by
board-id/msm-id, so the shim boot image must carry all of them byte for byte.
The Mi MIX 2S stock boot.img has 14 of them after the gzip stream.

  polaris_dtb.py --from-boot backup/boot.img out/polaris-dtb.bin
  polaris_dtb.py dtb/polaris_stock/fdt out/polaris-dtb.bin   # dir of .dtb files
"""
import os
import struct
import sys
import zlib

FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def boot_parts(path):
    b = open(path, "rb").read()
    if b[:8] != b"ANDROID!":
        sys.exit("error: %s is not an Android boot image" % path)
    (ks, ka, rs, ra, ss, sa, ta, ps, ver, osv) = struct.unpack_from("<10I", b, 8)
    if ks == 0:
        sys.exit("error: boot image has an empty kernel")
    if ps < 512 or ps > 65536 or ps & (ps - 1):
        sys.exit("error: weird page size %d" % ps)
    return b, ps, ks, ver


def kernel_end(stream):
    """Return (decompressed_size, offset just past the gzip stream)."""
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(stream)
    out += d.flush()
    if not d.eof:
        sys.exit("error: truncated gzip stream in kernel")
    consumed = len(stream) - len(d.unused_data)
    return len(out), consumed


def dtb_sizes(blob, start):
    offs = []
    pos = start
    while True:
        pos = blob.find(FDT_MAGIC, pos)
        if pos < 0:
            break
        if pos + 8 > len(blob):
            break
        total = struct.unpack_from(">I", blob, pos + 4)[0]
        if total < 0x30 or pos + total > len(blob):
            pos += 4
            continue
        offs.append((pos, total))
        pos += total
    return offs


def model_of(dtb):
    # crude: find "model\0<len>" property value; fall back to any Xiaomi string
    i = dtb.find(b"model\0")
    if i > 0 and i + 16 < len(dtb):
        ln = struct.unpack_from(">I", dtb, i + 6)[0]
        if 0 < ln < 128 and i + 10 + ln <= len(dtb):
            return dtb[i + 10:i + 10 + ln].split(b"\0")[0].decode("utf-8", "replace")
    j = dtb.find(b"Xiaomi")
    if j > 0:
        s = dtb[j:j + 90].split(b"\0")[0]
        return s.decode("utf-8", "replace")
    return "?"


def main():
    args = sys.argv[1:]
    if args and args[0] == "--from-boot":
        boot, out = args[1], args[2]
        blob, ps, ks, ver = boot_parts(boot)
        kernel = blob[ps:ps + ks]
        if kernel[:2] == b"\x1f\x8b":
            dsize, end = kernel_end(kernel)
            print("kernel: gzip, %d bytes decompressed, stream ends at 0x%x"
                  % (dsize, end))
        else:
            end = 0
            print("kernel: not gzip, scanning whole blob")
        found = dtb_sizes(kernel, end)
        if not found:
            sys.exit("error: no FDT blobs found after the kernel")
        # The stock image carries DTBs for every SDM845 Xiaomi model
        # (polaris / dipper / equuleus / ursa). ABL matches by board-id, and
        # only polaris entries can ever match a Mi MIX 2S, so keep the image
        # small by default: append the polaris ones only. --all keeps every DTB.
        keep_all = "--all" in args
        polaris = [(o, t) for o, t in found if b"Polaris" in kernel[o:o + t]]
        chosen = found if keep_all else polaris
        if not keep_all and not polaris:
            sys.exit("error: no Polaris DTBs found (use --all to keep every DTB)")
        data = b"".join(kernel[o:o + t] for o, t in chosen)
        with open(out, "wb") as f:
            f.write(data)
        print("polaris_dtb: %d of %d DTBs (%s), %d bytes -> %s"
              % (len(chosen), len(found), "all" if keep_all else "Polaris only",
                 len(data), out))
        for n, (o, t) in enumerate(chosen):
            d = kernel[o:o + t]
            mod = model_of(d)
            if mod == "?":
                j = d.find(b"Xiaomi")
                if j > 0:
                    mod = d[j:j + 90].split(b"\0")[0].decode("utf-8", "replace")
            print("  [%02d] off 0x%-8x size %-7d %s" % (n, o, t, mod))
        return

    src, out = args[0], args[1]
    files = []
    if os.path.isdir(src):
        files = [os.path.join(src, n) for n in sorted(os.listdir(src))
                 if os.path.isfile(os.path.join(src, n))]
    else:
        files = [src]
    data = b""
    n = 0
    for f in files:
        d = open(f, "rb").read()
        if d[:4] != FDT_MAGIC:
            continue
        data += d
        n += 1
    if not n:
        sys.exit("error: no FDT files found in %s" % src)
    open(out, "wb").write(data)
    print("polaris_dtb: %d DTBs, %d bytes -> %s" % (n, len(data), out))


if __name__ == "__main__":
    main()
