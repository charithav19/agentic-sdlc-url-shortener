# Phases 14–15 verification assertions

- Scheduler execution is bounded by an `asyncio.Semaphore` and configurable from
  one to 32 concurrent stages; the local default is three.
- Both configured fan-outs place all three independent children in `RUNNING`
  concurrently when the cap is three.
- A cap of two produced an observed maximum of exactly two active executors.
- PostgreSQL row locks plus a partial unique active-claim index prevent duplicate
  claims for the same stage and generation.
- Each claim has an owner, UUID fencing token, and expiry. Only that current,
  unexpired token can commit success or failure.
- Competing schedulers executed and committed the same stage exactly once.
- `IMPLEMENTATION` success alone did not release `BUILD_VALIDATION` while
  `TEST_DESIGN` was delayed and `RUNNING`.
- After `TEST_DESIGN` succeeded, the join changed build from `BLOCKED` to `READY`.
- Claim and readiness changes append causal audit events with stage identity,
  generation, attempt, and before/after state.

These assertions do not claim restart recovery, automatic lease reclamation,
candidate workspace merging, compatible artifact joins, scheduler cancellation,
or live model execution.
