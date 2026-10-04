# ADR-005: Best-effort redirect analytics

Status: accepted for Phase 4.

Successful redirects enqueue a click event for a bounded in-process worker.
The redirect never waits for the analytics database write. The worker uses a
separate PostgreSQL transaction, a two-second transaction and statement
timeout, and a three-second connection acquisition timeout. The pool has two
threads and a queue of 100 by default, with validated configuration bounds.
Writer exceptions and queue rejection increment separate Micrometer counters
and log only the trace ID and failure class; they do not change the redirect.

An event stores link ID, UTC timestamp, request trace ID, optional HTTP(S)
referrer **origin** and a coarse user-agent category. Referrer path, query,
fragment and credentials, raw user-agent, and client IP are not retained. The
analytics endpoint groups persisted events by UTC date. Metadata reads and
unsuccessful redirects do not submit events.

This is best-effort delivery. A process stop, full queue, unavailable database
or write timeout can lose an event; counts can lag behind redirects. There is
no exactly-once claim, durable message broker or replay of failed events.
Events currently have no automatic retention cleanup so the demonstrated
history is preserved. Database growth and a formal retention/deletion policy
must be resolved before production deployment. The queue and worker settings
can be tuned per instance, but instances do not share queue state.

Synchronous writes would couple redirect availability and latency to
PostgreSQL. Kafka or Redis would add infrastructure outside the assignment's
constraints. A background worker is the smallest design that keeps redirects
available while making loss and failure visible.
