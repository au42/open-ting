#!/usr/bin/env bash
# Rebuild every derived artifact from firmware/uf2/*.uf2.
# Idempotent: safe to re-run. Nothing here touches the device.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== extracting UF2 =="
python3 scripts/uf2extract.py firmware/uf2/*.uf2 -o extracted

echo
echo "== extracting romfs (/rom) =="
for d in extracted/*/; do
    seg="$d/seg_100e0000.bin"
    [ -f "$seg" ] && python3 scripts/romfs_extract.py "$seg" -o "$d/rom"
done

echo
echo "== disassembling main segment =="
for d in extracted/*/; do
    n=$(basename "$d")
    ./scripts/disasm.sh "$d/seg_10000000.bin" 0x10000000 "disasm/${n}.asm"
done

echo
echo "== extracting strings =="
mkdir -p strings
LLVM="${LLVM:-/opt/homebrew/opt/llvm/bin}"
for d in extracted/*/; do
    n=$(basename "$d")
    "$LLVM/llvm-strings" -n 4 "$d/seg_10000000.bin" | sort -u > "strings/${n}.txt"
done
wc -l strings/*.txt | tail -5

echo
echo "done."
