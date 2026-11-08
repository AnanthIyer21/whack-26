"""Live view of what the face extension sees, as text. No window, no images saved.

    python tools/face_debug.py                 # real camera via Aaron's vision (needs camera permission)
    python tools/face_debug.py --seconds 120

Twice a second it prints: face fps and ms per frame, how many faces, the state
(calibrating / covered / no face / the held expression), each expression's level
(>= 0 means "on") and head turn/tilt relative to your usual position. Every time an
expression FIRES (what GRIP-9000 would react to) it prints a >>> line.

Try: neutral for 10 s (nothing should fire), then smile, laugh, open your mouth in
shock, frown, turn your head away, and hold your fist in front of your mouth.
"""

import argparse
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import shared  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=90.0)
    args = parser.parse_args()

    import face
    import vision
    stop = shared.stop_event
    threading.Thread(target=vision.run, args=(stop,), name="vision", daemon=True).start()
    threading.Thread(target=face.run, args=(stop,), name="face", daemon=True).start()
    print("Starting camera and face model... (Ctrl+C to stop)")
    started = time.monotonic()
    next_print = started + 0.5
    try:
        while time.monotonic() - started < args.seconds:
            try:
                event = shared.events.get(timeout=0.05)
                if event["type"] == shared.FACE:
                    print(">>> FIRED: " + event["expression"] + " (strength " + str(event["strength"]) + ")")
            except Exception:
                pass
            now = time.monotonic()
            if now >= next_print:
                next_print = now + 0.5
                fs = shared.get_face_state()
                d = face.diag
                levels = ""
                for name in ("smiling", "laughing", "shock", "frowning", "looking_away"):
                    value = d.get("levels", {}).get(name)
                    if value is not None:
                        levels += "  " + name + "=" + ("%+.2f" % value)
                print("%5.1fs  %4.1f fps %5.1f ms  faces=%d  %-12s yaw=%+5.1f pitch=%+5.1f |%s" % (
                    now - started, d.get("fps", 0.0), d.get("ms", 0.0), d.get("faces", 0),
                    str(d.get("state")), fs.yaw, fs.pitch, levels))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        time.sleep(0.3)


if __name__ == "__main__":
    main()
