# Multi-unit preemption — design notes

As we evolve `PreemptiveResource` the single-unit preemption model (preempt
one holder to satisfy one incoming requester) may not be sufficient. This
document collects the deep-dive discussion about multi-unit preemption: why
it matters, design options, test ideas, and an incremental implementation
strategy.

## Why multi-unit preemption is needed
- Some resources are divisible or allocated in multi-unit chunks. Examples:
  - A worker pool where a single task may occupy multiple workers (e.g. a
    parallel job requiring k cores). A high-priority job that needs k cores
    might need to free multiple currently-held cores.
  - Network bandwidth or bandwidth slices where a high-priority flow wants a
    larger share and must preempt multiple low-priority flows to get enough
    capacity.
  - Containers that represent storage or fluid where requests specify amounts
    (units) rather than single tokens; a request for amount M may require
    preempting several smaller holders.

## When to prefer multi-unit preemption
- When requests can ask for more than one unit at a time (``request(n)``),
  and the system must satisfy such requests promptly when a higher-priority
  request arrives.
- When per-unit fairness is not sufficient and end-to-end latency for some
  high-priority operations is critical.
- When holdings are preemptible (holders can be interrupted and later
  rescheduled) and the system semantics tolerate partial revocation.

## Design options (semantics)
- Atomic multi-unit preemption (coarse): preempt whole holders one-by-one
  until enough units are freed to satisfy the incoming request. Holders are
  chosen by victim selection policy (lowest priority, oldest, smallest
  allocation, etc.). This is simpler and deterministic.
- Partial-holder preemption (fine-grained): if holders themselves hold >1
  units, evict a subset of units from a holder. This requires holders to be
  represented as collections of unit allocations and adds bookkeeping.
- Batched preemption: collect victims until required units freed, then
  atomically revoke them and grant the request at a single event time.
  This is preferable where the request must see a consistent view of
  resource allocation.
- Soft preemption: inform victims they should release voluntarily (a
  cooperative approach), useful when immediate interruption is disruptive.

## API sketches
- request_with(units=1, priority=0, preemptible=False, preempt_policy="atomic")
  - `units`: how many units this request needs.
  - `preemptible` (for holders): whether the holder can be preempted.
  - `preempt_policy`: "atomic" (default), "partial", "batched", or "soft".
- Preempted exception may carry context: which units were revoked and a
  recommended backoff or retry value.

## Test ideas (TDD)
- `test_multi_unit_preempt_atomic`: holder A holds 2 units, B holds 1 unit
  (capacity 3). A high-priority request asks for 3 units; expect A and B to
  be preempted (or victims chosen by policy) and the request to acquire 3
  units at the preemption time. Victims should receive `Preempted`.
- `test_partial_holder_preempt`: a holder with 4 units is partially preempted
  to free 2 units for a high-priority request of 2 units; confirm holder is
  left with 2 units and receives `Preempted(partial=True)` or a specialized
  exception describing the partial eviction.
- `test_batched_atomicity`: ensure the request is only granted after all
  victims are revoked and that no interleaving resumes can observe a
  transient inconsistent state.
- `test_soft_preemption`: verify victims are signaled and may choose to yield
  the units; test both voluntary and refused release paths.

## Implementation notes and pitfalls
- Data structures: maintain `allocated` as a list of allocation records
  (proc, token, units, priority, preemptible). Use a heap/list for waiters
  and a sequence counter for ordering.
- Victim selection: implement selectable strategies (lowest priority, oldest
  preemptible, smallest-holder-first). Keep selection deterministic using the
  seq counter.
- Atomicity and race conditions: prefer to collect all victims first, then
  (in a single deterministic step) mark them revoked, schedule `Preempted`
  exceptions for those victims, and only after scheduling the revocations
  allocate and schedule the new request. This avoids race windows where one
  victim's revival could steal capacity mid-preemption.
- Interaction with timeouts/cancellation: if a waiting request times out while
  preemption is in progress, ensure either the preemption is rolled back or
  victims are left in a consistent state (e.g., reallocated or left revoked).
  Tests must cover these races.
- Complexity: preempting many holders can be O(n) in the number of holders;
  for very large systems consider indexing by priority or maintaining
  preemptible sets to optimize selection.

## Recommended incremental approach
1. Add `units` to `Request` and `Token` semantics (default 1). Update the
   simple `Resource` to accept multi-unit requests but without preemption.
2. Implement atomic multi-unit preemption in `PreemptiveResource`:
   - When a high-priority multi-unit request arrives, scan allocations for
     preemptible victims in priority order until enough units collected.
   - Mark victims revoked and schedule `Preempted` for each victim in the
     same simulation time, then grant the incoming request.
3. Add tests for atomic multi-unit preemption and run the suite.
4. If needed, add partial-holder preemption (more complex bookkeeping) and
   soft preemption later.

## Operational concerns
- Logging/observability: preemption events are disruptive—add structured
  logs or events (time, requester, victims, units) to help debug simulations.
- Backoff & retry: provide patterns/tests for victims to re-request (with
  backoff) so the system's steady-state behavior can be evaluated.

## Conclusion

Multi-unit preemption is a powerful mechanism when requests specify amounts
and high-priority operations need immediate capacity. Start with atomic,
deterministic semantics (simpler and easier to test). Expand to partial or
cooperative preemption only when necessary.
