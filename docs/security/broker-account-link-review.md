# Broker account linking security review checklist

Status: required before any production broker-link endpoint or official broker adapter is enabled.

## Credential handling

- [ ] Credentials, refresh tokens, PINs and OTPs are never accepted through Telegram.
- [ ] Credential material is never returned by REST, included in an audit payload, or sent to logs.
- [ ] The selected production `SecretStore` uses a managed secret service or HSM-backed key
      hierarchy; the in-memory Fernet adapter is not deployed in production.
- [ ] Encryption keys are supplied only through the deployment secret manager, rotated under a
      documented process, and never committed to configuration files.
- [ ] A credential revocation at the broker also triggers `unlink` and secret-store revocation.

## Account authorization

- [ ] Broker authorization uses an official, documented account-linking flow for the selected
      account type.
- [ ] The server verifies that the authenticated owner is allowed to link the broker account.
- [ ] Link, relink and unlink actions have immutable audit records without secret values.
- [ ] A revoked link cannot retrieve a credential or submit an order.

## Operations and incident response

- [ ] Access to credential retrieval is restricted to the approved broker adapter workload.
- [ ] Production secret-store failures fail closed and raise an operational alert without
      revealing sensitive context.
- [ ] An incident runbook covers token exposure, account unlinking, key rotation and broker
      escalation contacts.
- [ ] Compliance/security owners approve the completed checklist before any real-order release.
