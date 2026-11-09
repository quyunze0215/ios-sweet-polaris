#!/usr/bin/env python3
"""Extract the payload of an IMG4/IM4P container (DER-wrapped: IA5String type,
IA5String name, OCTET STRING payload).

  im4p-extract.py DeviceTree.d22ap.im4p d22ap.payload
The payload is usually LZFSE (starts with bvx2/bvxn) and must then be decoded
with the lzfse CLI to get the raw Apple Device Tree.
"""
import sys


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = open(src, "rb").read()
    i = b.find(b"IM4P")
    if i < 0:
        sys.exit("error: no IM4P magic in %s" % src)
    p = i + 4

    def ia5(p):
        if b[p] != 0x16:
            sys.exit("error: expected IA5String at 0x%x, got 0x%02x" % (p, b[p]))
        ln = b[p + 1]
        return b[p + 2:p + 2 + ln].decode(), p + 2 + ln

    kind, p = ia5(p)
    name, p = ia5(p)
    if b[p] != 0x04:
        sys.exit("error: expected OCTET STRING at 0x%x, got 0x%02x" % (p, b[p]))
    ln = b[p + 1]
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(b[p + 2:p + 2 + n], "big")
        p += 2 + n
    else:
        p += 2
    payload = b[p:p + ln]
    open(dst, "wb").write(payload)
    print("im4p: type=%s name=%s payload=%d bytes -> %s (head %s)"
          % (kind, name, len(payload), dst, payload[:4]))


if __name__ == "__main__":
    main()
