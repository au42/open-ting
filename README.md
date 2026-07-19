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

## Device behaviour learned by testing

None of this is documented by TE. All of it was established on hardware.

- **`SAMPLE` must sit at row 3 or later in a chain.** Earlier rows build and load
  correctly — verified by reading the chain back out of the engine — but the
  sample never sounds. TE pads short chains with `NONE` rows specifically to push
  `SAMPLE` down: factory preset 0 is `NONE -> DELAY -> NONE -> SAMPLE`.
- **Samples must be explicitly loaded** with `spl.rom(i)` or `spl.load_wav()`.
  A replacement `main.py` that skips this leaves the slots holding stale engine
  state: samples work on clean, misbehave inside an fx chain, and **hard-crash
  the device** when triggered into one.
- **`ui.leds(n, s)` is a cumulative bar anchored at the top**, not an LED
  selector. `leds(0)` lights the top LED, `leds(3)` all four, `leds(-1)` none.
  Individual LEDs cannot be addressed and the bar cannot fill from the bottom.
- **Modulation `depth` is in the target parameter's own units**, not normalised
  0..1. The factory robot preset uses `depth 800.0` on `SSB.frequency` (range
  ±20000). A depth of `0.5` on a Hz-valued parameter is inaudible.
- **`SSB.frequency` shifts the spectrum linearly in Hz.** Negative bases push a
  voice's fundamental below 0 Hz where it folds back and cancels, so such a
  preset is near-silent until modulation lifts it above zero.
- **`sw(3)` reads pressed from roughly handle 0.37 upward**, not only at the end
  of travel. Gate any full-pull action on `sw(3)` **and** `handle >= 0.9`.
- **`fx.list_preset()` / `list_loaded()` / `timing()` / `map()` print, they do
  not return.** They appear to return `None` because their output goes to the
  REPL, which has no endpoint.
- **`fx.timing()` is a DSP profiler.** It reveals an undocumented `compressor`
  and `noisegate` permanently in the chain, together consuming roughly 3400 of
  ~3505 cycles.
- **MicroPython dicts are not insertion-ordered here.** Iterating a modulation
  dict applied `depth` before `param`. Set `row`, `param`, `depth` explicitly —
  TE's own `config.json` loader has the same latent bug.
- **`io.BytesIO` has no `truncate()`** in this build. Track a read offset instead.

### Getting a console

The MicroPython REPL is compiled into the firmware but has no CDC endpoint, so
prints and tracebacks go nowhere. `os.dupterm()` redirects that stream — but it
only accepts a **native** stream object. A Python class with `write()`/
`readinto()` raises `OSError: stream operation not supported`. `io.BytesIO`
works:

```python
import os, io
buf = io.BytesIO()
os.dupterm(buf)
fx.list_preset(0)          # now capturable
data = buf.getvalue()      # no truncate(); track an offset to drain
```

This is the only way to see anything the firmware prints, and it is what made
the preset behaviour above discoverable.

## Example: `examples/main.py`

A complete replacement for TE's `main.py`, written against the native `ui`,
`spl` and `fx` modules. It reimplements TE's button and preset state machine —
including the `primed` debounce counters — so the device still behaves normally,
then layers new behaviour on top.

**Controls** are unchanged: orange cycles effects, green cycles samples, white
triggers the selected sample.

**Presets** (orange cycles `clean → 1 → 2 → 3 → 4`):

| # | Chain | Lever does |
|---|---|---|
| 1 | `NONE → HARMONY → NONE → SAMPLE` | pitch **up** to +7 semitones |
| 2 | `NONE → HARMONY → NONE → SAMPLE` | pitch **down** to −5 semitones |
| 3 | `HIGHPASS → LOWPASS → DIST → DELAY → SAMPLE` | opens the lo-fi filter |
| 4 | `SSB → DELAY → REVERB → HIGHPASS → SAMPLE` | sweeps the robot frequency shift |

Preset 4 is TE's factory robot preset copied verbatim. It is **not** autotune —
the firmware has no pitch detection, `HARMONY` is a fixed-ratio shifter, and
Python has no access to audio buffers, so pitch correction is not reachable
without writing new DSP in C.

**LED behaviour:**

- The sample LED blinks fast for ~1.2 s after a sample is triggered. This is a
  timer, not real playback length — no playback-complete event exists.
- The effect LED blinks progressively faster as the lever is pulled. A lever
  movement of ≥0.1 restarts the blink immediately rather than waiting out the
  current cycle.
- Pulling the lever fully home **bypasses the effect** and turns the LEDs into a
  level meter. The meter's input is a **placeholder** driven by `ui.shaker()`,
  because nothing in `ui`/`spl`/`fx` returns microphone amplitude — see
  `input_level()`.

There is also an inert reference stub, `_sensors_reference_unused()`, documenting
how the accelerometer and battery telemetry would be used. It is never called.

## Installing

Copy `examples/main.py` onto the device's USB volume as `main.py`. It shadows
`/rom/main.py` at boot — no reflashing, no bootloader, no OTP involvement.

```sh
cp examples/main.py /Volumes/TINGDISK/main.py
sync
diskutil eject /Volumes/TINGDISK     # or just unplug
```

Then power-cycle: press the small button above the USB-C port to switch off, and
push the handle to start again. `main.py` is only read at boot.

Two practical notes:

- **Verify the copy.** Writes to this device have failed mid-copy and silently
  left the previous file in place, which looks exactly like a change that did
  not work. Hash it: `shasum -a256 examples/main.py /Volumes/TINGDISK/main.py`.
- **macOS writes AppleDouble files.** `xattr -c` the source first, or `dot_clean`
  the volume afterwards, to avoid wasting part of the 1 MB on `._main.py`.

## Recovery

Mass storage is served **below** Python, so the drive enumerates regardless of
what a script does. Recovery is always:

1. Connect USB
2. Delete `main.py` from the volume
3. Power-cycle — the device boots TE's own `/rom/main.py` and behaves as stock

If the unit will not start at all, hold **green + white** while powering on.
That is TE's documented recovery path.

### ⚠️ Never write to flash from `main.py`

`main.py` runs on **every boot, including with USB connected.** Writing to the
filesystem while the host has the volume mounted puts two writers on the same
flash. In testing this corrupted the FAT, truncated every file to a block
boundary, and left the device repeatedly dropping off the USB bus. `fsck` could
only repair by discarding contents.

TE's own `main.py` only ever *reads* at boot, which is why stock firmware never
hits this.

If a diagnostic must write, it has to either run on **batteries with USB
unplugged** — powering the unit off before reconnecting — or be gated behind a
button held at boot so it cannot fire unintentionally. `DEBUG` in
`examples/main.py` defaults to `False` for this reason.

## Next steps

### Samples are not modulated by the effects

The headline limitation: **the effects process the microphone only.** Samples
play back clean, in parallel with the processed voice. Preset 3 will not make
your sample lo-fi, and preset 4 will not robotise it.

This is a structural conflict between two rules, not a bug in the example:

1. TE's documentation says effects placed **after** the `SAMPLE` block process
   the sample, and a `SAMPLE` block at the end of the chain stays dry.
2. Testing established that `SAMPLE` **must sit at row 3 or later** or it does
   not play at all.

Every factory preset resolves this by putting `SAMPLE` last — which means
**TE's own samples are always dry too.** Placing `SAMPLE` early enough for
effects to follow it puts it below row 3, where playback stops.

### The untested experiment

Both rules can in principle be satisfied at once: put `SAMPLE` at **row 3** and
the effects you want applied to it at **rows 4 and beyond**.

Nothing in the factory firmware does this, so it is genuinely unknown. It hinges
on a distinction the existing evidence cannot settle, because every configuration
tested so far had `SAMPLE` last:

- If the real rule is "`SAMPLE` at row ≥ 3", this works and gets you modulated
  samples.
- If the real rule is "`SAMPLE` must be **last**", it will not play, and
  per-chain sample effects are impossible this way.

That single test discriminates between them and is the highest-value next
experiment in this repo.

### Other unexplored routes

- **`BUS` routing.** `config.json` documents a `BUS` key for parallel effect
  chains, and none of the factory presets we dumped use it. A bus split is the
  most plausible mechanism for processing the sample independently of the mic.
- **Runtime chain edits.** `fx.add`, `fx.insert`, `fx.remove` and `fx.clear`
  mutate a *live* chain. An effect could in principle be inserted after `SAMPLE`
  at the moment a sample is triggered, and removed afterwards.
- **`fx.flip` and `fx.map`** are unidentified. `fx.map` takes a string and prints
  a parameter schema; `fx.flip` is unknown.

### Also open

- **A real input level meter.** Nothing in `ui`/`spl`/`fx` returns audio
  amplitude, so the meter currently reads `ui.shaker()`. Whether any ADC channel
  carries a microphone envelope is untested — ADC channels 0–2 stream
  continuously at ~3 ms, which makes them plausible candidates.
- **`ui.led_control` / `ui.led_level`** are unprobed. They are the likely path to
  per-LED or brightness control, which `ui.leds()` cannot do.
- **An intermittent crash** has been observed with no traceback captured, since
  logging is disabled by default. Diagnosing it needs button-gated logging so
  capture can never fire while USB is connected.
- **USB MIDI / HID / audio** need custom firmware. `machine` and `usb` are not in
  the build, so USB cannot be reconfigured from Python, and TE's OTP
  white-labelling disables PICOBOOT so `picotool` cannot reach the device.

