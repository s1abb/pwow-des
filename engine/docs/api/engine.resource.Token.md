# Class Token

## Module
`engine.resource`

## Class Declaration
```py
class Token:
    def __init__(self, resource, proc, name=None, allocated_at=None)
```

## Description
`Token` represents a granted allocation from a `Resource`. It is a
context-manager: exiting the context (``with (yield req) as tok:``) will
call `resource.release(token=tok)`.

Attributes:
- `resource` — owning `Resource` instance
- `proc` — the owning process
- `name` — optional friendly name attached to the request
- `allocated_at` — timestamp when the token was allocated (env.now)
- `id` — small numeric id for monitoring/pretty-printing

Usage example:

```py
with (yield res.request()) as tok:
    # do work while holding the resource
    pass
```
