# Class Interrupt

## Module
`engine.interrupt`

## Class Declaration
```py
class Interrupt(Exception):
    pass
```

## Description
Simple exception class used to signal an interrupt into a `Process`.
Delivered via `Environment.interrupt(proc, exc=Interrupt())` or by
calling `Process.interrupt()`.
