# Paper confirmation UI security review (Phase 13)

## Delivered server-side flow

`PaperConfirmationService` creates a short-lived immutable snapshot of a draft
intent plus its approved pre-trade risk decision. A secure UI must present that
exact snapshot, obtain an owner-bound TOTP factor, then request confirmation using
the authenticated session identity. The service creates a `PaperTradeApproval`
only after the factor verifies. Its server-generated idempotency key remains bound
to exactly that intent.

Expired pending requests are terminally marked `EXPIRED` by the expiry job. An
expired request cannot create an approval and therefore cannot reach the paper
broker. The job contains no Telegram call and can run even without a Telegram chat
target.

## Deliberate boundary

There is no web confirmation endpoint or browser form in this phase. StockTrace
currently has an application API key but no authenticated web-session model that
can prove which `owner_id` is making a request. Accepting an owner identifier from
JSON would make the confirmation flow impersonable. Telegram remains notification
and deep-link only; it can never confirm, alter, or submit a trade.

## Preconditions before enabling a UI route

1. Add durable user/session authentication whose server-side principal is mapped to
   `TradeIntentDraft.owner_id`; never accept that ID from the browser body.
2. Use HTTPS-only secure, `HttpOnly`, `SameSite` session cookies and server-side
   CSRF protection for all confirmation mutations.
3. Render the immutable intent, risk-policy version, expiry timestamp and warnings;
   do not let the browser edit symbol, side, quantity, price, account or idempotency
   key after creation.
4. Use a durable transactional repository and idempotency uniqueness constraint;
   replace the in-memory repository before any non-demo deployment.
5. Keep TOTP enrollment/recovery in a managed encrypted secret store. Never return,
   log, or deliver a TOTP secret via HTTP or Telegram.
6. Keep the official broker gate in ADR-0001 closed. This flow authorizes only the
   in-memory paper broker and contains no real broker endpoint or credential.
