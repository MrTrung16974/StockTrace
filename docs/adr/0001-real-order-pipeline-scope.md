# ADR 0001: Real order pipeline scope and broker selection gate

- Status: proposed — broker decision required
- Date: 2026-08-12
- Decision owners: StockTrace product owner, compliance owner, security owner
- Related roadmap: Real Order Pipeline, Phase 1

## Context

StockTrace currently monitors Vietnamese equities and produces data-backed analysis
through Telegram and REST. It does not have a broker execution adapter, an order
database, an account-linking flow, or a secure confirmation UI.

Real order placement is materially different from a market-data command. An order
must be traceable from its evidence snapshot through the user confirmation and
broker response, and failures must never create a duplicate order or an unknown
portfolio state.

This ADR fixes the safe initial boundary. It deliberately does not select a broker
until its official execution capability and contractual requirements are verified.

## Decisions

### 1. Product boundary for the first execution release

The intended first real-money scope is **cash equities and fund certificates listed
on HOSE, HNX, and UPCOM**, subject to the selected broker's officially documented
capabilities.

The first release excludes:

- derivatives, warrants, bonds, ETFs with special order rules, and IPO/rights flows;
- margin borrowing, short selling, securities lending, and leveraged products;
- market/conditional/algorithmic order types until the broker adapter supports and
  tests their exact validation rules;
- multi-account bulk trading, discretionary trading, and any order initiated solely
  by an LLM.

The only initial real order type is a broker-supported **limit order**. Quantity,
lot size, tick size, price band, session and cancellation rules remain broker- and
exchange-specific validations enforced before submit.

### 2. Broker selection is a hard gate

No real broker adapter will be implemented until one broker provides all of the
following in writing or in official developer documentation:

1. A supported order-placement API for the intended account type, not an
   undocumented mobile/web endpoint.
2. An approved authentication and account-linking mechanism suitable for a server
   application, with token revocation/rotation.
3. API access for balances, positions, order status and fills.
4. A sandbox, test environment, or another broker-approved test procedure.
5. Clear rate limits, idempotency behavior, error codes and webhook/polling model.
6. Contractual permission for this integration and a named support/escalation path.

Until this gate is cleared, StockTrace proceeds only through suggestion, replay and
paper-trading phases. `PaperBroker` is the mandatory execution adapter for all
early development and demos.

#### Broker capability matrix

Use this matrix for each candidate. A candidate fails Phase 1 if any row marked
**mandatory** is `No`, `Unknown`, or supported only through an undocumented
endpoint. The matrix must link to the broker's official document or written
confirmation; a sales claim or community SDK is not evidence.

| Capability | Required | Candidate evidence | Result |
| --- | --- | --- | --- |
| Official server-side order API for cash equities | Mandatory | URL/contact/case ID | Pending |
| Allowed account type and integration contract | Mandatory | Terms/approval | Pending |
| Official authorization, revoke and token rotation | Mandatory | Auth documentation | Pending |
| Balance, buying power and current positions | Mandatory | API documentation | Pending |
| Submit, cancel, query order and fill status | Mandatory | API documentation | Pending |
| Sandbox or broker-approved non-production test route | Mandatory | Sandbox guide/contact | Pending |
| Documented error/status codes and rate limits | Mandatory | API documentation | Pending |
| Idempotency support or documented duplicate-order mitigation | Mandatory | API documentation/contact | Pending |
| Webhook or safe polling/reconciliation model | Mandatory | API documentation | Pending |
| HOSE/HNX/UPCOM support | Mandatory | Product/API scope | Pending |
| Limit-order validation: tick, lot, price band and session | Mandatory | API/exchange mapping | Pending |
| Test/support escalation owner | Mandatory | Contact/case ID | Pending |
| Derivatives, margin and conditional orders | Optional, excluded initially | Product/API scope | Not evaluated |

#### Phase 1 acceptance criteria

Phase 1 can be marked `accepted` only when one named broker has passed every
mandatory row, the product owner has accepted the first-release boundary, and the
security/compliance owners have signed the checklist. Otherwise, work is limited
to non-execution phases and `PaperBroker`.

### 3. Account model and authority

The initial model is one account owner linked to one broker account at a time. A
user can revoke the link at any moment. Shared accounts, advisor-managed accounts
and trading on behalf of another person are out of scope.

Broker credentials, refresh tokens, PINs and OTP secrets must never be received in
Telegram, written to logs, committed to configuration, or stored in plaintext in
PostgreSQL. Account linking must use the broker's official authorization flow and a
server-side secret store with encryption at rest.

### 4. Confirmation and automation policy

Every real-money order starts as a `TradeIntent` draft. It can be submitted only
after a secure web UI displays an immutable intent snapshot and the account owner
passes 2FA. The confirmation has a short expiry and a unique idempotency key.

Telegram may notify the owner and carry a deep link to this UI. Telegram messages,
button callbacks and chat replies are never trade authorization.

Automatic execution is disabled by default. It is not enabled by an environment
variable alone. A future pilot additionally requires paper-trading evidence, a
stored manual approval record, per-user/symbol/notional limits and a live global
kill switch.

### 5. Deterministic decision boundary

`TradeIntent` may only be created by deterministic application code after data
quality and pre-trade risk checks. LLM providers may explain an already-created
suggestion but cannot supply symbol, side, quantity, order type, price, approval or
submit action.

Every suggestion, risk decision, confirmation and broker submission must have an
audit snapshot that records the input data, source/time/freshness, rule version,
decision trace, user action and broker response.

## Compliance and security checklist before Phase 10

The project owner must obtain and record answers for the selected broker and
deployment environment before real API work begins:

- Is programmatic order entry available to this application and account type?
- What user authorization, 2FA and consent record does the broker require?
- Which exchanges, instruments, sessions and order types are permitted?
- Are order idempotency keys supported; if not, how is duplicate submission safely
  prevented and reconciled?
- What are the API rate limits, outage semantics, sandbox constraints and support
  escalation process?
- Which customer, order and audit data must be retained, where may it be stored and
  for how long?
- What data-protection, encryption, access-control and incident-reporting
  obligations apply to the deployment?
- Does the proposed user flow require additional legal/compliance review before
  launch?

This is an engineering decision document, not legal advice. Compliance approval is
an explicit release gate.

## Consequences

- Development can safely start with Phase 2 contracts and Phase 9 paper trading,
  while real execution remains blocked.
- The broker is swappable behind `BrokerExecutionPort`; no domain or rule-engine
  logic depends on a broker SDK.
- A broker without an official supported order API is rejected, even if a reverse-
  engineered endpoint appears to work.
- The scope grows only after exchange/broker rules are represented in tests and
  pre-trade controls.

## Open decision required

Select the first broker candidate and supply its official API/developer/contact
documentation. Once supplied, this ADR can change from `proposed` to `accepted`
and the broker capability matrix can be completed.
