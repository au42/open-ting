# EP-2350 custom main.py
#
# Drop on TINGDISK as main.py. Shadows /rom/main.py at boot.
# Recovery: delete the file over USB, or hold green+white at startup.
#
# Presets (orange button cycles: clean -> 0 -> 1 -> 2 -> 3):
#   0  PITCH BEND UP    lever raises pitch up to +1 octave
#   1  PITCH BEND DOWN  lever lowers pitch down to -1 octave
#   2  LO-FI VOCAL      band-limited + driven + slap delay; lever sweeps filter
#   3  ROBOT            ring mod; lever sweeps carrier frequency
#
# Slot 3 is NOT autotune. The firmware has no pitch detection -- HARMONY is a
# fixed-ratio shifter, and Python has no access to audio buffers. Robot voice
# is the closest sound reachable without writing new DSP in C.
#
# LEDs:
#   sample LED blinks fast while a sample is playing
#   effect LED blinks slower->faster as the lever is pulled further
#   LEDs become a top-anchored level meter while the lever is pressed fully home
#   (effect bypassed). The meter's level source is a PLACEHOLDER -- see
#   input_level(); there is no audio-amplitude API in this firmware yet.

import os
import io
import sys
import ui
import fx
import spl
from time import sleep_ms, ticks_ms, ticks_diff

# ---------------------------------------------------------------- config ----
# Measured with probe_ui2.py (see device/ui_probe.txt):
#   handle()  -> float 0.0 (released) .. 1.0 (fully home)
#   sw(0..2)  -> the three buttons, ACTIVE LOW (0 == pressed)
#   sw(3)     -> end-of-travel switch, ACTIVE LOW. Reads 0 only at high handle
#                positions and never below; this is the full-pull button.
#   sw(4)     -> "handle engaged" (light pull / mic enable), NOT positional.
#                TE gates preset changes on sw(4)==0 so presets can't change
#                mid-performance -- that logic is preserved below.
FULL_PULL_SW = 3        # measured, not inferred
SW_PRESSED = 0          # active low
FULL_PULL_MIN_H = 0.9   # sw(3) alone triggers from ~0.37; require real full travel
SAMPLE_BLINK_MS = 1200  # assumed one-shot length; no playback-complete event exists
BLINK_SLOW_MS = 500     # lever released
BLINK_FAST_MS = 60      # lever nearly home
SAMPLE_BLINK_MS_ON = 70 # sample-playing blink half-period
# DEBUG writes to flash from the main loop. Doing that while the host has the
# volume mounted over USB corrupted the filesystem -- host and device both
# writing the same flash. Leave this OFF unless running on batteries with USB
# UNPLUGGED, and delete crash.txt before reconnecting.
DEBUG = False           # capture stdout/tracebacks to /fat/crash.txt
DEBUG_POLL_MS = 500     # how often to check for new output to persist
LOOP_MS = 20            # was 10; slower idle loop = less CPU stolen from DSP
METER_UPDATE_MS = 100   # how often the meter re-reads level; 10 Hz is plenty
HANDLE_JUMP = 0.1       # lever movement that restarts the blink immediately


# ------------------------------------------------------------- debug capture ----
# The REPL is compiled into this firmware but has no CDC endpoint, so anything
# printed -- including tracebacks -- normally goes nowhere. os.dupterm() accepts
# a native stream, so stdout is captured to RAM and flushed to flash only when
# something has actually been written. No output means no writes, so this costs
# no flash wear during normal operation.
_dbg = None
_dbg_off = 0


def _dbg_start():
    global _dbg
    if not DEBUG:
        return
    try:
        _dbg = io.BytesIO()
        os.dupterm(_dbg)
    except Exception:
        _dbg = None


def _dbg_flush():
    """Persist anything newly printed. Called from the main loop."""
    global _dbg_off
    if _dbg is None:
        return
    try:
        d = _dbg.getvalue()          # BytesIO has no truncate() in MicroPython
        if len(d) <= _dbg_off:
            return
        new = d[_dbg_off:]
        _dbg_off = len(d)
        try:
            fh = open("/fat/crash.txt", "a")
        except Exception:
            return
        try:
            fh.write(new.decode() if isinstance(new, bytes) else new)
        finally:
            fh.close()
    except Exception:
        pass


def _dbg_exc(where, e):
    """Print a traceback into the captured stream."""
    if _dbg is None:
        return
    try:
        print("\n--- exception in %s ---" % where)
        sys.print_exception(e)
    except Exception:
        pass


_dbg_start()


# ------------------------------------------------------------ preset defs ----
# (effect, {params}), plus optional handle modulation {row, param, depth}.
#
# HYPOTHESIS UNDER TEST: SAMPLE must sit at row 3 or later.
#
# Evidence, from reading the factory presets back (device/build.txt, dump.txt):
#   factory 0:  NONE -> DELAY -> NONE -> SAMPLE                (SAMPLE row 3)
#   factory 1:  NONE -> DELAY -> REVERB -> SAMPLE              (SAMPLE row 3)
#   factory 3:  SSB -> DELAY -> REVERB -> HIGHPASS -> SAMPLE   (SAMPLE row 4)
# TE pads unused slots with NONE rather than shortening the chain -- preset 0
# needs only DELAY yet still places it at row 1 with NONE either side. Padding
# is not something you write by accident.
#
# Our presets 0/1 had SAMPLE at row 1 and did not play samples. Preset 3 had it
# at row 3 and did. Presets 0/1 are now padded to the factory shape. Preset 2 is
# unchanged (SAMPLE already at row 4, same as factory 3) -- if it still fails
# while 0/1 recover, row position is not the whole story.
#
# The chains verifiably build correctly either way (every fx call returns ok and
# reads back with the right params), so this is about how the ENGINE interprets
# row position, not about the build.
#
# depth is in the target parameter's own units, not normalised 0..1 -- the
# factory robot preset uses depth 800.0 on SSB.frequency (range +/-20000).
#
# HARMONY.pitch is a ratio: 12*log2(ratio) semitones.
#     2.00 = +12    1.50 = +7    1.335 = +5    1.0 = unison    0.75 = -5
BEND_UP = 0.5           # 1.0 -> 1.5   (+7 semitones)
BEND_DOWN = -0.25       # 1.0 -> 0.75  (-5 semitones)
SAMPLE_LEVEL = 1.0      # clean preset uses 1.00; factory fx presets use 0.50

PRESETS = [
    # 0 -- pitch bend up.  NONE padding puts SAMPLE at row 3 (factory shape).
    # NONE rows carry a "nothing" param; the factory presets set it (20.0 at
    # row 0, 1.0 at row 2) rather than leaving it unset. Mirrored here in case
    # it is real state and not just stale union memory in the readback.
    ([("NONE", {"nothing": 20.0}),
      ("HARMONY", {"pitch": 1.0, "dry-level": 0.0}),
      ("NONE", {"nothing": 1.0}),
      ("SAMPLE", {"speed": 1.0, "level": SAMPLE_LEVEL})],
     {"row": 1, "param": "pitch", "depth": BEND_UP}),

    # 1 -- pitch bend down
    ([("NONE", {"nothing": 20.0}),
      ("HARMONY", {"pitch": 1.0, "dry-level": 0.0}),
      ("NONE", {"nothing": 1.0}),
      ("SAMPLE", {"speed": 1.0, "level": SAMPLE_LEVEL})],
     {"row": 1, "param": "pitch", "depth": BEND_DOWN}),

    # 2 -- lo-fi EDM vocal. Unchanged: SAMPLE already at row 4.
    ([("HIGHPASS", {"cutoff": 0.28}),
      ("LOWPASS", {"cutoff": 0.55}),
      ("DIST", {"amount": 9.0, "mix": 0.55,
                "highpass-cutoff": 0.2, "lowpass-cutoff": 0.6}),
      ("DELAY", {"time": 0.18, "echo": 0.32,
                 "wet-level": 0.3, "dry-level": 1.0}),
      ("SAMPLE", {"speed": 1.0, "level": SAMPLE_LEVEL})],
     {"row": 1, "param": "cutoff", "depth": 0.45}),

    # 3 -- robot: TE's factory preset 3, copied EXACTLY (all five rows).
    #
    # The diagnostic proved our four-row version builds and loads correctly --
    # SAMPLE present at row 3 with level 1.00, handle bound to SSB.frequency,
    # LOADED identical to BUILT, trigger raising no exception -- yet samples
    # stayed silent. Since the chain is provably right, the remaining variable
    # is the chain itself, so use the one TE ships and is known to play samples.
    #
    # Note this restores base frequency -300 and modulation from row 0. Both
    # were things I changed away from on theories that the diagnostic has now
    # undermined; TE's values ship and work, so they get the benefit of doubt.
    ([("SSB", {"frequency": -300.0}),
      ("DELAY", {"time": 0.4, "lowpass-cutoff": 0.9, "highpass-cutoff": 0.4,
                 "wet-level": 0.0, "dry-level": 1.0, "echo": 0.0,
                 "cross-feed": 0.5, "balance": 0.8}),
      ("REVERB", {"dry-level": 1.0, "wet-level": 0.0, "time": 0.5,
                  "spring-mix": 1.0, "highpass-cutoff": 0.0}),
      ("HIGHPASS", {"cutoff": 0.2}),
      ("SAMPLE", {"speed": 1.0, "level": SAMPLE_LEVEL})],
     {"row": 0, "param": "frequency", "depth": 800.0}),
]


def load_samples():
    """Load the four sample slots. THIS IS NOT OPTIONAL.

    TE's own main.py does this in examine_drive(); an earlier version of this
    file omitted it entirely, which left the slots holding whatever the C engine
    had lying around. Symptoms were: samples fine on clean, erratic inside an fx
    chain, and a hard crash when triggering into a chain -- unless a clean-preset
    trigger had "warmed up" the slot first.

    Per-slot: prefer <n>.wav from the drive, fall back to the factory ROM sample.
    Each slot is independent so one bad WAV cannot take the others down.
    """
    try:
        os.chdir("/fat")
    except Exception:
        pass

    for i in range(4):
        loaded = False
        try:
            g = open("%d.wav" % (i + 1), "rb")
            try:
                loaded = bool(spl.load_wav(i, g, 0))
            finally:
                g.close()
        except Exception:
            loaded = False
        if not loaded:
            try:
                spl.rom(i)          # factory sample
            except Exception:
                pass


def build_presets():
    for pos, (chain, handle) in enumerate(PRESETS):
        try:
            fx.preset_mods_disable(pos)
            for j, (effect, params) in enumerate(chain):
                fx.preset(pos, j, effect)
                for k, v in params.items():
                    fx.preset_param(pos, j, k, float(v))
            fx.preset(pos, len(chain), "END")
            if handle:
                # Explicit order: row, then param, then depth. Iterating
                # handle.items() applied depth before param, since MicroPython
                # dicts are not insertion-ordered.
                for k in ("row", "param", "depth"):
                    if k in handle:
                        fx.preset_handle(pos, k, handle[k])
        except Exception:
            pass    # a bad slot must not take down the whole boot


# ------------------------------------------------------------------ state ----
sam_pos = 0
fx_pos = -1
sam_primed = 0
fx_primed = 0

playing_until = 0
bypassed = False


def handle_norm():
    """Lever position, 0.0 (released) .. 1.0 (home). Already normalised in fw."""
    try:
        h = ui.handle()
    except Exception:
        return 0.0
    return 0.0 if h < 0.0 else (1.0 if h > 1.0 else h)


def full_pull():
    """True only at genuine end of travel.

    sw(3) alone is NOT sufficient. The original switch probe recorded
    sw(3)==0 across handle 0.37..1.00, which was dismissed at the time as
    sampling skew -- it was not. Using sw(3) by itself made full_pull() true
    at half pull, firing the bypass and swapping to the clean preset, which is
    why effects "stopped working" partway through the lever.

    Requiring the lever to also be near the top of its range makes this robust
    whatever sw(3)'s exact semantics turn out to be.
    """
    try:
        if ui.sw(FULL_PULL_SW) != SW_PRESSED:
            return False
    except Exception:
        return False
    return handle_norm() >= FULL_PULL_MIN_H


_led_state = None


def set_leds(f, s):
    """Write the LED bar, skipping redundant calls.

    The meter and idle paths previously re-wrote the same value every loop pass
    (~100 writes/sec). Caching cuts that to writes that actually change
    something -- one candidate for the rhythmic clicking heard while idle.
    """
    global _led_state
    st = (f, s)
    if st == _led_state:
        return
    _led_state = st
    try:
        ui.leds(f, s)
    except Exception:
        pass


# --- LED level meter --------------------------------------------------------
# DISCOVERED IN TESTING: ui.leds() does not address individual LEDs. It draws a
# cumulative bar anchored at the TOP:
#
#     ui.leds(0, s) -> top LED only
#     ui.leds(1, s) -> top two
#     ui.leds(2, s) -> top three
#     ui.leds(3, s) -> all four
#     ui.leds(-1, s) -> none
#
# There is no way to light one LED in isolation, and no way to fill upward from
# the bottom. The meter therefore grows DOWNWARD from the top; bottom-up is not
# achievable with this API.
#
# This also explains the uneven brightness seen with the earlier multiplexed
# bar: every index includes the top LED, so it was lit on every multiplex pass
# while lower LEDs were lit on only some of them. Multiplexing was never needed
# either -- the firmware draws the bar itself in one call.

_meter_last = 0
_meter_bars = 0


def input_level():
    """Return 0.0 .. 1.0 for the meter.

    PLACEHOLDER -- this is NOT audio level. No function in ui/spl/fx returns
    microphone amplitude, so there is currently no real source to read. Driven
    from ui.shaker() for now so the meter visibly moves.

    Once probe_level.py identifies an ADC channel that tracks loudness, swap
    the body for something like:

        v = ui.adc(CH)                  # CH from the probe results
        return (v - FLOOR) / (CEIL - FLOOR)     # clamped 0..1

    and everything downstream keeps working unchanged.
    """
    try:
        v = ui.shaker() * 12.0          # shaker rests near 0.02; scale to taste
    except Exception:
        return 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def meter(now):
    """Show input level as a top-anchored bar, re-read every METER_UPDATE_MS.

    One ui.leds() call per update. No multiplexing, so brightness is even and
    there is nothing to flicker.
    """
    global _meter_last, _meter_bars
    if ticks_diff(now, _meter_last) >= METER_UPDATE_MS:
        _meter_last = now
        b = int(input_level() * 4.0 + 0.5)
        _meter_bars = 0 if b < 0 else (4 if b > 4 else b)

    if _meter_bars <= 0:
        set_leds(-1, sam_pos)
    else:
        set_leds(_meter_bars - 1, sam_pos)


# --------------------------------------------------------------- callback ----
def python_callback(message):
    try:
        _callback(message)
    except Exception as e:
        _dbg_exc("python_callback", e)


def _callback(message):
    global sam_pos, fx_pos, sam_primed, fx_primed, playing_until
    mess_type = message >> 16
    mess_val = message & 0xFFFF

    # --- ADC filter -------------------------------------------------------
    # ADC channels 0-2 stream continuously at roughly 3 ms intervals. During
    # probing they filled a 400-event buffer in 1.3 s and drowned out every
    # button event. Nothing here consumes them -- the lever is read by polling
    # ui.handle() in the main loop instead -- so they are pure callback
    # overhead and get dropped before any further work.
    #
    # TO UNDO: delete the two lines below. To keep just one channel instead,
    # replace them with an equality test on the specific type, e.g.
    #     if mess_type & 0xF0 == 0x10 and mess_type != 0x10:
    #         return                      # keeps ADC 0, drops 1 and 2
    # Channel numbering is `mess_type & 0x0F`, so 0x10/0x11/0x12 are ADC 0/1/2.
    if mess_type & 0xF0 == 0x10:
        return

    if mess_type == 1:
        if mess_val == 0:
            spl.trigger(-1, sam_pos, True)
            playing_until = ticks_ms() + SAMPLE_BLINK_MS
        if mess_val == 1 and ui.sw(4) == 0:
            sam_primed = 10
        if mess_val == 2 and ui.sw(4) == 0:
            fx_primed = 10

    elif mess_type == 2:
        if mess_val == 0:
            spl.trigger(-1, sam_pos, False)
        if mess_val == 1:
            sam_primed = 0
        if mess_val == 2:
            fx_primed = 0

    elif mess_type == 3:
        if fx_primed > 0:
            fx_primed -= 1
            if fx_primed == 0:
                fx_pos += 1
                if fx_pos >= 4:
                    fx_pos = -1
                fx.load_preset(fx_pos)
                set_leds(fx_pos, sam_pos)
                if DEBUG:
                    try:
                        print("\n=== LOADED fx_pos=%d ===" % fx_pos)
                        fx.list_loaded(0)
                    except Exception as _e:
                        _dbg_exc("load dump", _e)
        if sam_primed > 0:
            sam_primed -= 1
            if sam_primed == 0:
                sam_pos += 1
                if sam_pos >= 4:
                    sam_pos = 0
                set_leds(fx_pos, sam_pos)

    elif mess_type == 4 and mess_val == 1:
        # drive ejected -- reload samples and presets, as stock firmware does
        load_samples()
        build_presets()
        fx.load_preset(fx_pos)


# ============================================================================
# REFERENCE STUB -- NOT CALLED, NOT WIRED IN. Deliberately inert.
#
# Sketches how the accelerometer and battery telemetry would be used. Nothing
# below runs: the function is never invoked and nothing references it. It is
# here as documentation of the measured API, not as working behaviour.
# ============================================================================
def _sensors_reference_unused():
    # --- accelerometer ------------------------------------------------------
    # ui.acc() -> [x, y, z] as signed ints. Measured resting value was
    # [3488, 864, 16192] with the unit face-up, so ~16384 counts == 1 g and the
    # z axis is vertical. Axis signs/orientation past that are unverified.
    #
    #   x, y, z = ui.acc()
    #
    # Tilt: with the device upright, gravity moves out of z and into x/y, so
    # a rough tilt magnitude is the horizontal component:
    #
    #   tilt = (x * x + y * y) ** 0.5 / 16384.0     # 0.0 flat .. 1.0 on edge
    #
    # That could drive a parameter the way the lever does, e.g.
    #
    #   fx.param(row, "cutoff", 0.2 + 0.7 * tilt)
    #
    # ui.shaker() already returns a scalar shake intensity (0.019 at rest), so
    # for shake detection prefer it over differentiating acc() by hand. The FX
    # engine also has a native shake modulator -- fx.preset_shake(pos, ...) --
    # which runs in C at audio rate and will feel far better than anything
    # polled from Python at 100 Hz.

    # --- battery ------------------------------------------------------------
    # ui.get_vbat() -> float volts, PER CELL. Measured 1.688 on fresh alkalines.
    # Rough alkaline AAA curve: 1.6 fresh, 1.2 half, 1.0 effectively flat.
    # ui.get_vbus() -> USB rail; read 1.31 with USB unplugged, so it is NOT a
    # clean "is USB connected" flag and would need characterising before use.
    #
    #   v = ui.get_vbat()
    #   if v < 1.15:
    #       pass        # warn: e.g. flash all LEDs briefly at startup
    #
    # Note the firmware already blinks an LED and refuses to start on low
    # battery (see readme), so a custom warning is mostly useful for logging
    # or for fading out gracefully mid-set rather than for protection.
    #
    # ui.get_temp() returned 92.85 -- units unconfirmed. Plausibly degrees F
    # (~33.8 C) or a raw sensor count. Do not trust it as Celsius.
    pass


# ------------------------------------------------------------------- boot ----
load_samples()
build_presets()

if DEBUG:
    # Dump what actually landed in the engine for every preset. fx.list_preset
    # prints rather than returns, so this only works with dupterm attached.
    try:
        for _p in range(4):
            print("\n=== built preset %d ===" % _p)
            fx.list_preset(_p)
    except Exception as _e:
        _dbg_exc("boot dump", _e)
fx.load_preset(fx_pos)
set_leds(fx_pos, sam_pos)
ui.callback(python_callback)

# -------------------------------------------------------------- main loop ----
last_toggle = ticks_ms()
led_on = True
last_h = 0.0
_dbg_last = ticks_ms()

while True:
    now = ticks_ms()
    h = handle_norm()
    fully = full_pull()

    # bypass while the lever is pressed fully home
    if fully and not bypassed:
        bypassed = True
        if DEBUG:
            try:
                print("bypass ON  h=%.2f sw3=%r fx=%d" % (h, ui.sw(FULL_PULL_SW), fx_pos))
            except Exception:
                pass
        try:
            fx.load_preset(-1)
        except Exception:
            pass
    elif not fully and bypassed:
        bypassed = False
        if DEBUG:
            try:
                print("bypass OFF h=%.2f sw3=%r fx=%d" % (h, ui.sw(FULL_PULL_SW), fx_pos))
            except Exception:
                pass
        try:
            fx.load_preset(fx_pos)
        except Exception:
            pass

    if fully:
        # lever pressed fully home: LEDs become an input level meter.
        # Multiplexed every pass -- no toggle gating, it needs the full rate.
        meter(now)

    elif now < playing_until:
        # sample playing -- fast blink on the sample LED
        if ticks_diff(now, last_toggle) >= SAMPLE_BLINK_MS_ON:
            last_toggle = now
            led_on = not led_on
            set_leds(fx_pos, sam_pos if led_on else -1)

    elif h > 0.03 and fx_pos >= 0:
        # lever engaged -- blink effect LED, rate rising linearly with pull.
        #
        # A moved lever restarts the cycle immediately rather than waiting for
        # the current on/off period to expire. Without this the new rate only
        # took effect at the next toggle, so fast lever moves felt laggy.
        period = BLINK_SLOW_MS - (BLINK_SLOW_MS - BLINK_FAST_MS) * h
        if abs(h - last_h) >= HANDLE_JUMP:
            last_h = h
            last_toggle = now
            led_on = True
            set_leds(fx_pos, sam_pos)
        elif ticks_diff(now, last_toggle) >= int(period):
            last_toggle = now
            led_on = not led_on
            set_leds(fx_pos if led_on else -1, sam_pos)

    else:
        if not led_on:
            led_on = True
            set_leds(fx_pos, sam_pos)

    # Metering multiplexes one LED per pass, so it needs a much tighter loop
    # than the rest of the UI to avoid visible flicker.
    if DEBUG and ticks_diff(now, _dbg_last) >= DEBUG_POLL_MS:
        _dbg_last = now
        _dbg_flush()

    sleep_ms(LOOP_MS)
