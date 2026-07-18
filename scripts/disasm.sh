#!/usr/bin/env bash
# Disassemble an EP-2350 flash segment as Cortex-M33 Thumb-2.
#
#   ./disasm.sh <seg.bin> [load_addr] [outfile]
#
# llvm-objdump cannot disassemble raw binaries directly (no GNU -b binary), so
# the segment is first wrapped into an ELF with llvm-objcopy at the right VMA.
# Default load address is 0x10000000 (RP2350 XIP flash base).
set -euo pipefail

LLVM="${LLVM:-/opt/homebrew/opt/llvm/bin}"
OBJCOPY="$LLVM/llvm-objcopy"
OBJDUMP="$LLVM/llvm-objdump"
for t in "$OBJCOPY" "$OBJDUMP"; do
    [ -x "$t" ] || { echo "missing $t (set LLVM=)" >&2; exit 1; }
done

BIN="${1:?usage: disasm.sh <seg.bin> [load_addr] [outfile]}"
ADDR="${2:-0x10000000}"
OUT="${3:-disasm/$(basename "${BIN%.bin}").asm}"
mkdir -p "$(dirname "$OUT")"
ELF="${OUT%.asm}.elf"

# Wrap raw flash image in an ELF, relocating .data -> .text at the load address.
"$OBJCOPY" -I binary -O elf32-littlearm \
    --rename-section .data=.text,code,alloc,load,readonly \
    "$BIN" "$ELF"

# RP2350 = dual Cortex-M33 (Armv8-M Mainline, DSP + FPU).
# VMA is applied here rather than in objcopy: --change-section-address is
# accepted but has no effect on a binary-input ELF, whereas --adjust-vma works.
"$OBJDUMP" -d \
    --triple=thumbv8m.main-none-eabi \
    --mcpu=cortex-m33 \
    --no-show-raw-insn \
    --adjust-vma="$ADDR" \
    "$ELF" \
  | sed -E 's/_binary_[A-Za-z0-9_]*_start/fw/g' > "$OUT"

printf 'disassembled %s @ %s\n  elf -> %s\n  asm -> %s (%s lines, %s)\n' \
    "$(basename "$BIN")" "$ADDR" "$ELF" "$OUT" \
    "$(wc -l < "$OUT" | tr -d ' ')" \
    "$(du -h "$OUT" | cut -f1)"
