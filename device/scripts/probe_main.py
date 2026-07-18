# EP-2350 API probe -- RUN ON BATTERIES, USB UNPLUGGED.
# Writes the full runtime API surface to /fat/probe.txt, then blinks to signal done.
# Does not touch USB config, fx, or spl. Nothing here is irreversible.

import sys

lines = []


def rec(s):
    lines.append(str(s))


rec("=== EP-2350 probe ===")
for label, expr in (("version", "sys.version"), ("implementation", "sys.implementation"),
                    ("platform", "sys.platform"), ("path", "sys.path"),
                    ("modules", "sorted(sys.modules.keys())")):
    try:
        rec(f"{label}: {eval(expr)}")
    except Exception as e:
        rec(f"{label}: ERR {e!r}")

# The three TE native modules are the interesting ones; the rest map the sandbox.
MODS = ("ui", "spl", "fx", "machine", "rp2", "vfs", "os", "time", "utime", "json",
        "gc", "io", "array", "struct", "math", "micropython", "usb", "usb.device",
        "uctypes", "select", "_thread", "random", "binascii", "errno")

for name in MODS:
    try:
        m = __import__(name)
        rec(f"\n[{name}] {', '.join(sorted(dir(m)))}")
    except Exception as e:
        rec(f"\n[{name}] MISSING ({e!r})")

# USBDevice is the path to enabling CDC/REPL -- capture its constants exactly.
try:
    import machine
    u = machine.USBDevice
    rec(f"\n[machine.USBDevice] {', '.join(sorted(dir(u)))}")
    for c in sorted(d for d in dir(u) if d.startswith("BUILTIN")):
        rec(f"  {c} = {getattr(u, c)!r}")
except Exception as e:
    rec(f"\n[machine.USBDevice] ERR {e!r}")

try:
    import os
    rec(f"\n[cwd] {os.getcwd()}")
    rec(f"[listdir /fat] {os.listdir('/fat')}")
except Exception as e:
    rec(f"\n[fs] ERR {e!r}")

try:
    with open("/fat/probe.txt", "w") as f:
        f.write("\n".join(lines))
    ok = True
except Exception:
    ok = False

# Signal completion: fast blink = wrote probe.txt, slow = write failed.
try:
    import ui
    from time import sleep_ms
    d = 100 if ok else 600
    for i in range(40):
        ui.leds(3, 3) if i % 2 else ui.leds(-1, 0)
        sleep_ms(d)
except Exception:
    pass
