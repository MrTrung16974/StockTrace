# Order lifecycle and reconciliation review (Phase 15)

`OrderLifecycle` is an immutable, checksum-protected state machine. It permits
only `PENDING → PARTIALLY_FILLED → FILLED`, `PENDING → REJECTED`, and
`PENDING/PARTIALLY_FILLED → CANCELLED`. Each fill has a unique broker fill ID,
quantity, price, and timestamp. Terminal orders cannot receive further fills.

`ReconciliationService` compares these confirmed fills with both the captured
internal portfolio baseline and broker account snapshot. It returns a portfolio
mutation plan only if account/owner/symbol match and broker quantity exactly equals
the expected result of the fill. Any mismatch yields `REQUIRES_REVIEW` and no plan.

The service does not submit orders or mutate a portfolio itself. A production
integration must persist the lifecycle and reconciliation snapshot, then apply a
plan exactly once in the same durable transaction. Until an official broker passes
ADR-0001, all integration remains paper-only.
