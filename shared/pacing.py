"""Frame pacing for the game loop that doesn't starve the other threads.

Why: on macOS, clock.tick(60) oversleeps (~39 fps), and clock.tick_busy_loop(60)
holds Python's global lock while it spins, cutting the vision and rival threads'
CPU by ~60% (a big import in the rival took 40 s instead of 1 s).

FramePacer sleeps for most of the frame, then spins the last ~1.5 ms with
sleep(0), which releases the lock. Measured: 60.0 fps, background threads at
full speed.

    pacer = shared.FramePacer(shared.FPS)
    while running:
        ...draw...
        pygame.display.flip()
        pacer.tick()
        fps = pacer.fps()
"""

import time

SPIN_WINDOW = 0.0015


class FramePacer:
    def __init__(self, fps):
        self.period = 1.0 / fps
        self.next_frame = time.perf_counter() + self.period
        self.last = time.perf_counter()
        self.recent = []

    def tick(self):
        """Wait until the next frame is due. Returns seconds since the previous tick."""
        while True:
            left = self.next_frame - time.perf_counter()
            if left <= 0:
                break
            if left > SPIN_WINDOW + 0.0005:
                time.sleep(left - SPIN_WINDOW)
            else:
                time.sleep(0)
        now = time.perf_counter()
        self.next_frame += self.period
        if now - self.next_frame > 0.1:
            # We fell badly behind (a hitch): don't try to catch up with a burst of frames.
            self.next_frame = now + self.period
        dt = now - self.last
        self.last = now
        self.recent.append(dt)
        if len(self.recent) > 60:
            self.recent.pop(0)
        return dt

    def fps(self):
        if not self.recent:
            return 0.0
        total = 0.0
        for dt in self.recent:
            total += dt
        if total <= 0:
            return 0.0
        return len(self.recent) / total
