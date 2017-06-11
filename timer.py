class EventLoopTimer:
    """
    Provide a simple mechanism for profiling blocks of asynchronous code.
    Uses the event loop's internal clock.
    """
    def __init__(self, event_loop):
        self.event_loop = event_loop

    def __enter__(self):
        self.start = self.event_loop.time()
        return self

    def __exit__(self, *args):
        self.end = self.event_loop.time()
        self.interval = self.end - self.start