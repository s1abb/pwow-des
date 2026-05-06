# FilterStore and predicate-based Store.get — design notes

Goal
- Provide a `FilterStore` variant (or predicate-parameter on `Store.get`) so
  processes can retrieve items matching a predicate, not only FIFO.

Why
- Many message-passing simulations require selective receive semantics
  (e.g., take the first message matching a tag). A FilterStore avoids
  application-level polling loops and integrates with the scheduler.

API sketches
- `class FilterStore(Store)`: inherits `Store` but supports `get(filter=None, ...)`.
- `get(filter=callable, timeout=None, priority=0)`: if `filter` is provided,
  `get` returns the first item matching the predicate; if none available it
  queues a `GetRequest` with the filter attached.

Behavior
- When a `put(item)` occurs, the store should prefer to satisfy the earliest
  waiting getter whose predicate matches the new item (respecting priority and
  seq ordering among matching getters).
- If several getters match, pick by (priority, seq) order among matchers.
- If no matching getters exist and there is space, append to the FIFO items.

Tests (TDD)
- `test_filterstore_basic`: put several items, `get(filter=...)` returns the
  first matching item.
- `test_filterstore_wait`: start a getter with a predicate when no matching
  item exists; later put a matching item and assert the getter is resumed.
- `test_filterstore_priority`: multiple getters with predicates matching an
  incoming item — ensure priority and seq ordering are respected.
- Timeouts/cancellation: ensure timed-out getters are skipped and that
  predicates are evaluated only against available items.

Implementation notes
- Extend GetRequest to carry an optional `filter` attribute and make the
  matching logic in `Store` check waiters whose `filter` returns True for the
  arriving item.
- To avoid scanning many predicates on every put, consider maintaining a
  small index or keep predicates on the waiter heap but accept an O(n) scan
  for now (simpler, acceptable for modest queues).
- Ensure predicate evaluation is side-effect free or documented (user's
  responsibility).
