# EP-2350 sensor logger -- RUN ON BATTERIES, USB UNPLUGGED.
#
# Captures the full ui.callback event stream (buttons + handle ADC) into RAM for
# ~30 s, then writes ONE file at the end. Single flash write, no wear concern.
#
# LEDs: solid-ish slow blink while recording, fast blink when written.
# During the 30 s window: press all three buttons a few times, and sweep the
# handle slowly through its full travel and back.

import ui
from array import array
from time import sleep_ms, ticks_ms, ticks_diff

MAX = 1500
ts = array("i", bytearray(4 * MAX))     # preallocated -- callback must not allocate
ev = array("i", bytearray(4 * MAX))
n = 0
t0 = ticks_ms()


def cb(message):
    global n
    if n < MAX:
        ts[n] = ticks_diff(ticks_ms(), t0)
        ev[n] = message
        n += 1


ui.callback(cb)

DUR = 30000
while ticks_diff(ticks_ms(), t0) < DUR and n < MAX:
    try:
        ui.leds(3, 3) if (ticks_diff(ticks_ms(), t0) // 500) % 2 else ui.leds(-1, 0)
    except Exception:
        pass
    sleep_ms(25)

ui.callback(0)

out = ["# EP-2350 sensor log", "# events=%d duration_ms=%d" % (n, DUR), "",
       "ms\ttype\tval\traw"]
for i in range(n):
    m = ev[i]
    out.append("%d\t0x%02x\t%d\t0x%08x" % (ts[i], (m >> 16) & 0xFFFF, m & 0xFFFF, m))

# Direct-read API surface: establishes ranges/units the event stream doesn't show.
out.append("\n# direct reads (post-capture snapshot)")
for name in ("handle", "handle_raw", "acc", "shaker", "get_vbat", "get_vbus", "get_temp"):
    try:
        out.append("%s() = %r" % (name, getattr(ui, name)()))
    except Exception as e:
        out.append("%s() ERR %r" % (name, e))

for i in range(8):
    try:
        out.append("sw(%d) = %r" % (i, ui.sw(i)))
    except Exception as e:
        out.append("sw(%d) ERR %r" % (i, e))
        break

for i in range(8):
    try:
        out.append("adc(%d) = %r" % (i, ui.adc(i)))
    except Exception as e:
        out.append("adc(%d) ERR %r" % (i, e))
        break

ok = True
try:
    with open("/fat/sensors.txt", "w") as f:
        f.write("\n".join(out))
except Exception:
    ok = False

try:
    d = 100 if ok else 600
    for i in range(40):
        ui.leds(3, 3) if i % 2 else ui.leds(-1, 0)
        sleep_ms(d)
except Exception:
    pass
