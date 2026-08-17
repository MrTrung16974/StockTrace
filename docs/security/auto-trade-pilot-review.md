# Limited auto-trading pilot review (Phase 14)

## Gate conditions

`AutoTradeGate` does not submit any order. It can only return an authorization
decision when every gate below passes for the same immutable draft intent:

1. The pilot configuration is explicitly enabled and provides a finite symbol
   allowlist, per-order and per-day notional limits, and a daily order limit.
2. Phase-12 pre-trade risk is approved for the exact intent and account.
3. A separate, active manual approval record exists for the same owner/account.
   Environment configuration alone is insufficient.
4. That approval carries stable paper-trading evidence meeting the configured
   observation duration and completed-order minimum.
5. The symbol and accumulated daily exposure are within the pilot limits.

Every result is a checksum-protected audit snapshot with its decision identifier,
policy version and all failed block codes. The gate is deterministic and has no
dependency on an LLM, Telegram, browser callback or broker SDK.

## Deliberate release boundary

The project has no accepted official broker in ADR-0001, so the gate is not wired
to a broker and cannot cause a real order. `InMemoryAutoTradeApprovalRepository`
is development/test only. A production pilot first requires durable transactional
approval/audit storage, authenticated administrator action, a real kill switch,
and the broker/compliance acceptance gates in the ADR.
