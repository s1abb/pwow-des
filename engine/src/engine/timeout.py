class Timeout:
    """Yield this from a process to wait for a delay (seconds).

    Example:
        yield Timeout(3)
    """
    def __init__(self, delay=0.0):
        self.delay = float(delay)

    def __repr__(self):
        return f"<Timeout delay={self.delay}>"
