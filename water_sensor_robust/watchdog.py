import machine

class WatchdogTimer:
    def __init__(self, timeout_ms):
        # The maximum timeout for the Pico's watchdog is 8388 ms
        if timeout_ms > 8388:
            print(f"Warning: Watchdog timeout reduced from {timeout_ms}ms to 8388ms")
            timeout_ms = 8388
        self.timer = machine.WDT(timeout=timeout_ms)

    def feed(self):
        self.timer.feed()