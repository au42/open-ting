# EP-2350 proof-of-execution test
# Blinks the LEDs in a pattern the stock firmware never produces.
# Stock firmware sets LEDs statically on preset change; it never free-runs.
# If you see continuous blinking -> /fat/main.py executes -> live scripting surface.
# If the device behaves normally (or does nothing) -> frozen main.py won.
#
# Deliberately does NOT write to the filesystem (host may hold the MSC mount)
# and does NOT touch fx/spl, so there is nothing to corrupt.
# Recovery: delete this file over USB. MSC lives below Python and always enumerates.

try:
    import ui
except Exception:
    ui = None

try:
    from time import sleep_ms
except Exception:
    try:
        from utime import sleep_ms
    except Exception:
        def sleep_ms(ms):                 # crude fallback if no time module
            for _ in range(ms * 200):
                pass


def blink(n=60):
    for i in range(n):
        a, b = ((3, 3) if i % 2 else (-1, 0))
        try:
            ui.leds(a, b)
        except Exception:
            try:
                ui.led(a)                 # singular binding also exists
            except Exception:
                return False
        sleep_ms(150)
    return True


if ui is not None:
    blink()
