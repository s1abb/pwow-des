# Class Timeout

## Module
`engine.timeout`

## Class Declaration
```py
class Timeout:
    def __init__(self, delay: float = 0.0)
```

## Description
Lightweight yieldable used by `Process` to wait for a numeric delay.
Typical usage:

```py
yield Timeout(3)
```

Attributes:
- `delay` (float): the requested delay in simulation time units.

### __repr__
Returns a short string containing the delay value.
