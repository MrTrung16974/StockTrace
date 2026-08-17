# Trade pipeline disaster recovery runbook (Phase 17)

## Scope and invariant

StockTrace has no accepted official broker integration under ADR-0001. The only
executable adapter is `PaperBroker`; any `OfficialBrokerSkeleton` call fails
closed. Do not substitute reverse-engineered endpoints or a browser session during
an incident.

The core invariant is: **a missing/ambiguous broker outcome is never treated as a
fill, and no portfolio mutation is applied until reconciliation matches a confirmed
broker position snapshot.**

## Immediate response: suspected duplicate, mismatch, or broker outage

1. Activate the auto-trade kill switch using the double-authenticated operator
   endpoint. Record the incident ID in the mandatory reason. There is deliberately
   no release endpoint.
2. Preserve correlation/request IDs, `TradeIntent`, risk decision, confirmation,
   idempotency key, lifecycle checksum, reconciliation result and any broker raw
   response in the approved audit store. Never copy credentials, TOTP values, API
   keys or secrets into tickets or chat.
3. Treat `PENDING`, timeout, connection reset, malformed broker response and an
   unavailable order query as **unknown**. Do not retry with a new idempotency key.
4. Query the broker's official order-status and fill APIs by original client/order
   identifier once those APIs are approved. Reconcile each confirmed fill before
   applying a portfolio mutation.
5. Keep `REQUIRES_REVIEW` mismatches frozen. A human operator must compare broker
   balances/positions and audit data before correcting any tracked portfolio.

## Recovery and re-enable prerequisites

Re-enable automation only through a future separately reviewed release. It must
require: completed incident review, durable audit/reconciliation records, broker
confirmation that all ambiguous orders are terminal, a fresh manual pilot approval,
paper-trading revalidation, and independent security/compliance sign-off. Updating
an environment flag is never a recovery step.

## Phase-17 verification matrix

| Scenario | Automated evidence | Expected result |
| --- | --- | --- |
| Duplicate concurrent paper submit | `test_concurrent_duplicate_paper_submissions_fill_once` | One receipt and one account mutation |
| Unapproved broker/sandbox call | `test_unapproved_broker_outage_fails_closed_without_any_submission_path` | Explicit failure; no inferred execution |
| Kill-switch endpoint misuse | `test_auto_trade_control_api`, `test_auto_trade_control_security` | Two keys required; no release endpoint |
| Fill/portfolio mismatch | `test_reconciliation` | `REQUIRES_REVIEW`; no mutation plan |

The official broker sandbox scenario remains blocked until ADR-0001 records one
named broker, official sandbox access and the approval checklist. Run the same
matrix against that sandbox before any real-money release.
