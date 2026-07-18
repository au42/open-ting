# EP-2350 "ting" — firmware extraction & analysis

Reverse-engineering workspace for the Teenage Engineering EP-2350, a handheld
FX microphone built on a **Raspberry Pi RP2350**.

Everything here is derived from publicly downloadable firmware plus read-only
observation of the device. Nothing in `scripts/` writes to hardware.

## Key facts

| | |
|---|---|
| SoC | RP2350 (dual Cortex-M33, Armv8-M Mainline) |
| UF2 family | `0xe48bff59` (RP2350 ARM-S) |
| Toolchain | GCC 14.2.1, Pico SDK, TinyUSB |
| Runtime | **MicroPython 1.26.0-preview** (`v1.26.0-preview.136.g4085bf4de`) |
| USB (app mode) | VID `0x2367` PID `0x0620`, class `EF/02/01`, **MSC only** |
| USB (boot mode) | same VID/PID, class `00/00/00`, MSC only — **no PICOBOOT** |
| Flash image | `0x10000000`–`0x100b8000` (736 KB code) + `0x100e0000`–`0x100e4800` (18 KB romfs) |
| Encryption | none — entropy 6.82 bits/byte, plain ARM code |

### The application layer is Python

TE's entire app logic is a 236-line `main.py` stored as a real file in a
MicroPython ROMFS at `0x100e0000`, mounted at `/rom`. It is **not** frozen
bytecode, so it extracts losslessly — see `extracted/*/rom/main.py`.

Native C modules `ui`, `spl`, and `fx` provide the hardware bindings and expose
substantially more than `config.json` documents (live FX chain edits, chain
introspection, raw accelerometer, telemetry).

### Bootloader

`INFO_UF2.TXT`, `INDEX.HTM`, the `TING BOOT` volume label, and the custom USB
identity are all consistent with **RP2350 OTP white-labelling**, not a custom
bootloader — TE appears to use the stock mask-ROM UF2 bootloader with OTP-set
USB identity, and PICOBOOT disabled. Consequence: `picotool` cannot reach the
device over USB, so **OTP/secure-boot state is not readable without hardware**
(SWD, or forcing true BOOTSEL by holding flash CS low at power-on).

## Layout

```
firmware/uf2/        stock UF2 images, 1.0.5 – 1.0.8 (1.0.6 is unlisted but downloadable)
extracted/<ver>/     per-version derived artifacts
    seg_10000000.bin   main code segment
    seg_100e0000.bin   romfs segment
    flat.bin           segments concatenated
    padded.bin         0xFF gap-filled, loadable at 0x10000000
    layout.json        segment table, hashes, vector table, picobin offset
    rom/               files recovered from the romfs (main.py, README.md)
disasm/<ver>.asm     Cortex-M33 Thumb-2 disassembly (~302k lines each)
disasm/<ver>.elf     ELF wrapper used to produce it
strings/<ver>.txt    sorted unique strings
docs/                TE release notes per version
device/              artifacts captured from the physical unit
    scripts/           MicroPython scripts run on-device
```

## Usage

```sh
./scripts/build_all.sh                        # rebuild everything
python3 scripts/uf2extract.py f.uf2 -o out    # UF2 -> flat/padded/segment bins
python3 scripts/romfs_extract.py romfs.bin -o rom
./scripts/disasm.sh seg.bin 0x10000000 out.asm
```

Requires `python3` and LLVM (`brew install llvm`). Override the LLVM path with
`LLVM=/path/to/llvm/bin`.

## Notes and caveats

- **Cross-version binary diffing is useless.** ~544 KB of 753 KB differs between
  consecutive releases; builds are not reproducible and code shifts wholesale.
  Diff `rom/main.py` instead, which is meaningful and small.
- **The picobin item walk is unreliable.** `layout.json` reports the block offset
  (`0x10000138`) only. An earlier attempt to enumerate items past the first
  desynced and produced fictitious entries; do not trust item-level parses
  without reimplementing against the RP2350 datasheet.
- **`main.py` version history is readable.** 1.0.5 → 1.0.6 fixes `f.close(f)`
  (a `TypeError` that silently discarded every user's `config.json`), an
  off-by-one `pos > 4` → `pos >= 4`, and a `None` playmode guard.

## On-device code execution

Dropping `main.py` onto the USB mass-storage volume executes it at boot — it
shadows `/rom/main.py`. No reflashing, no bootloader, no OTP involvement.
Confirmed working. `device/scripts/` holds the scripts used so far.

Caveats learned the hard way:

- `machine` and `usb` modules are **not** in the build, so USB cannot be
  reconfigured from Python. `BUILTIN_CDC_MSC` in the qstr pool is a stock
  MicroPython leftover, not a live API. A `USB REPL` exists in the firmware but
  CDC is suppressed; enabling it requires custom firmware.
- Scripts that write to the filesystem must run **on batteries with USB
  unplugged** — otherwise the host's cached FAT and the device's writes fight.
- Never poll-and-write sensor data to flash. NOR flash is ~100k erase cycles;
  a 10 Hz logger would consume that in hours. Buffer in RAM, write once.
- Recovery from a bad script is always deleting it over USB — MSC is served
  below Python and enumerates regardless. `green + white` at boot is the
  documented backstop.
