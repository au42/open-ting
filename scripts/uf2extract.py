#!/usr/bin/env python3
"""Extract RP2350 UF2 firmware into flat, address-correct binaries.

Usage:
    ./uf2extract.py <file.uf2> [...] -o <outdir>

For each input produces, under <outdir>/<stem>/:
    seg_<addr>.bin      one file per contiguous flash segment
    flat.bin            all segments concatenated (no gap padding)
    padded.bin          gap-filled with 0xFF, loadable at the base address
    layout.json         segment table + metadata
"""
import argparse
import hashlib
import json
import os
import struct
import sys

UF2_MAGIC0 = 0x0A324655
UF2_MAGIC1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
BLOCK = 512

FAMILIES = {
    0xE48BFF56: "RP2040",
    0xE48BFF57: "absolute",
    0xE48BFF58: "data",
    0xE48BFF59: "RP2350 ARM-S",
    0xE48BFF5A: "RP2350 RISC-V",
    0xE48BFF5B: "RP2350 ARM-NS",
}

# RP2350 picobin block markers -- presence/absence is meaningful for secure boot.
PICOBIN_START = 0xFFFFDED3
PICOBIN_END = 0xAB123579


def parse_uf2(raw):
    """Yield (addr, payload, family) per block, validating magics."""
    if len(raw) % BLOCK:
        raise ValueError(f"not {BLOCK}-byte aligned: {len(raw)} bytes")
    for i in range(len(raw) // BLOCK):
        b = raw[i * BLOCK:(i + 1) * BLOCK]
        m0, m1, flags, addr, psz, bno, bcnt, fam = struct.unpack("<8I", b[:32])
        (mend,) = struct.unpack("<I", b[508:512])
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or mend != UF2_MAGIC_END:
            raise ValueError(f"block {i}: bad magic")
        if psz > 476:
            raise ValueError(f"block {i}: payload {psz} > 476")
        yield addr, b[32:32 + psz], fam


def segment(blocks):
    """Coalesce blocks into contiguous (start, bytes, family) segments."""
    segs = []
    start = None
    buf = bytearray()
    nxt = None
    cur_fam = None
    for addr, payload, fam in blocks:
        if nxt is None or addr != nxt or fam != cur_fam:
            if start is not None:
                segs.append((start, bytes(buf), cur_fam))
            start, buf, cur_fam = addr, bytearray(), fam
        buf += payload
        nxt = addr + len(payload)
    if start is not None:
        segs.append((start, bytes(buf), cur_fam))
    return segs


def find_picobin(data, base, limit=0x20000):
    """Locate the picobin block loop; report offset only (item walk is unreliable)."""
    for off in range(0, min(len(data), limit) - 4, 4):
        if struct.unpack_from("<I", data, off)[0] == PICOBIN_START:
            return {"file_offset": f"0x{off:x}", "flash_addr": f"0x{base + off:08x}"}
    return None


def process(path, outdir):
    raw = open(path, "rb").read()
    stem = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(outdir, stem)
    os.makedirs(dest, exist_ok=True)

    segs = segment(parse_uf2(raw))
    base = segs[0][0]
    end = segs[-1][0] + len(segs[-1][1])

    meta = {
        "source": os.path.basename(path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "uf2_bytes": len(raw),
        "uf2_blocks": len(raw) // BLOCK,
        "base_addr": f"0x{base:08x}",
        "end_addr": f"0x{end:08x}",
        "segments": [],
    }

    flat = bytearray()
    padded = bytearray(b"\xff" * (end - base))
    for start, data, fam in segs:
        name = f"seg_{start:08x}.bin"
        open(os.path.join(dest, name), "wb").write(data)
        flat += data
        padded[start - base:start - base + len(data)] = data
        meta["segments"].append({
            "file": name,
            "start": f"0x{start:08x}",
            "end": f"0x{start + len(data):08x}",
            "size": len(data),
            "family": FAMILIES.get(fam, f"0x{fam:08x}"),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    open(os.path.join(dest, "flat.bin"), "wb").write(flat)
    open(os.path.join(dest, "padded.bin"), "wb").write(padded)

    first = segs[0][1]
    meta["picobin"] = find_picobin(first, base)
    if len(first) >= 8:
        sp, pc = struct.unpack_from("<II", first, 0)
        meta["vector_table"] = {"initial_sp": f"0x{sp:08x}", "reset_handler": f"0x{pc:08x}"}

    json.dump(meta, open(os.path.join(dest, "layout.json"), "w"), indent=2)
    return meta, dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("uf2", nargs="+")
    ap.add_argument("-o", "--outdir", default="extracted")
    a = ap.parse_args()

    for p in a.uf2:
        try:
            meta, dest = process(p, a.outdir)
        except Exception as e:
            print(f"!! {p}: {e}", file=sys.stderr)
            continue
        print(f"\n{meta['source']}  ({meta['uf2_blocks']} blocks)")
        print(f"  sha256 {meta['source_sha256'][:16]}...")
        if meta.get("vector_table"):
            v = meta["vector_table"]
            print(f"  SP={v['initial_sp']}  reset={v['reset_handler']}")
        if meta.get("picobin"):
            print(f"  picobin @ {meta['picobin']['flash_addr']}")
        for s in meta["segments"]:
            print(f"  {s['start']}-{s['end']}  {s['size']:>8} B  {s['family']}")
        print(f"  -> {dest}")


if __name__ == "__main__":
    main()
