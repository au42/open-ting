#!/usr/bin/env python3
"""Extract files from a MicroPython ROMFS image (the /rom filesystem).

Layout, as observed in EP-2350 firmware:
    magic  d2 cd 31
    <varlen total_size>
    records: <varlen namelen> <name> <kind> <varlen datalen> <data>

varlen is big-endian 7-bit with 0x80 as the continuation bit.
kind 0x02 == data verbatim (the only kind seen here).

Usage:  ./romfs_extract.py <romfs.bin> -o <outdir>
"""
import argparse
import os
import sys

MAGIC = b"\xd2\xcd\x31"


def read_varlen(buf, i):
    """Return (value, next_index)."""
    v = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            return v, i
    raise ValueError("truncated varlen")


def extract(path, outdir):
    d = open(path, "rb").read()
    if not d.startswith(MAGIC):
        raise ValueError(f"bad magic {d[:3].hex()} (expected {MAGIC.hex()})")

    i = len(MAGIC)
    total, i = read_varlen(d, i)
    print(f"romfs: {len(d)} bytes on disk, declared payload {total}")

    os.makedirs(outdir, exist_ok=True)
    found = []
    # Records are not self-describing enough to walk blindly past padding, so
    # scan for plausible <namelen><name><0x02> headers instead.
    j = i
    while j < len(d) - 4:
        nlen = d[j]
        if 1 <= nlen <= 64:
            name = d[j + 1:j + 1 + nlen]
            if name.isascii() and all(32 <= c < 127 for c in name) and b"." in name:
                k = j + 1 + nlen
                if k < len(d) and d[k] == 0x02:
                    try:
                        dlen, k2 = read_varlen(d, k + 1)
                    except ValueError:
                        j += 1
                        continue
                    if 0 < dlen <= len(d) - k2:
                        blob = d[k2:k2 + dlen]
                        fn = name.decode()
                        open(os.path.join(outdir, fn), "wb").write(blob)
                        found.append((fn, dlen, k2))
                        print(f"  {fn:20s} {dlen:>7} bytes  @0x{k2:04x}")
                        j = k2 + dlen
                        continue
        j += 1

    if not found:
        print("!! no records recovered", file=sys.stderr)
        return 1
    print(f"-> {len(found)} file(s) into {outdir}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("romfs")
    ap.add_argument("-o", "--outdir", default="rom")
    a = ap.parse_args()
    sys.exit(extract(a.romfs, a.outdir))
