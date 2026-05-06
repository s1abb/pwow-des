This INDEX lists the example scripts in this directory and a one-line description.

anyof_timeout_demo.py
    - Demonstrates waiting on multiple events with a timeout (AnyOf/Timeout pattern).

carwash.py
    - Classic SimPy carwash example: customers, washing service, and queueing.

clock_demo.py
    - Simple clock/tick demonstration using Environment and periodic processes.

gas_station.py
    - Small station example where cars request fuel (uses Resource and Container).

interrupt_demo.py
    - Shows how Interrupts are raised to running processes and handled.

machine_shop.py
    - Machine shop example demonstrating preemption and priorities with resources.

preemption_demo.py
    - Demonstrates PreemptiveResource and how higher-priority requests preempt.

preemption_requeue_demo.py
    - Variant where preempted processes requeue themselves.

pretty_print_logger_demo.py
    - Shows pretty-printing logging helpers for processes and events.

pretty_print_logger_hold_demo.py
    - Variant of pretty-print logger demo showing hold/release semantics.

resource_priority_demo.py
    - Demonstrates resource priority queues: higher-priority requests win.

simple_timeout_demo.py
    - Minimal timeout demo: a process waits for a timeout and continues.

store_demo.py
    - Producer/consumer example using Store for buffering items.

Notes and consolidation suggestions:
- The demos are intentionally small. If you want fewer files, group related
  demos (preemption_* and preemption_requeue_* can be combined) or move
  very short snippets into a single `quick_demos.py` file.
- Consider adding a small pytest-based smoke test that imports and runs each
  example for a few simulated steps to ensure they remain runnable in CI.
