"""TOTP verification adapter using an encrypted secret-store boundary."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
from datetime import datetime

from stocktrace.domain.ports.secret_store import SecretStore

MIN_TOTP_DIGITS = 6
MAX_TOTP_DIGITS = 10


class TotpSecondFactorVerifier:
    """Verify RFC 6238-compatible base32 TOTP values without logging secrets.

    Production deployments must inject a durable KMS-backed ``SecretStore``. The
    encrypted in-memory implementation is strictly a development/test adapter.
    """

    def __init__(
        self,
        secret_store: SecretStore,
        *,
        time_step_seconds: int = 30,
        digits: int = 6,
        valid_window: int = 1,
    ) -> None:
        if time_step_seconds <= 0:
            raise ValueError("time_step_seconds must be greater than zero.")
        if digits < MIN_TOTP_DIGITS or digits > MAX_TOTP_DIGITS:
            raise ValueError("digits must be between 6 and 10.")
        if valid_window < 0:
            raise ValueError("valid_window must not be negative.")
        self._secret_store = secret_store
        self._time_step_seconds = time_step_seconds
        self._digits = digits
        self._valid_window = valid_window
        self._used_counters: set[tuple[str, int]] = set()
        self._lock = asyncio.Lock()

    async def verify(self, owner_id: str, code: str, *, verified_at: datetime) -> bool:
        """Return true once for an owner-bound TOTP code within the allowed window."""
        if (
            not owner_id.strip()
            or len(code) != self._digits
            or not code.isascii()
            or not code.isdigit()
        ):
            return False
        if verified_at.tzinfo is None or verified_at.utcoffset() is None:
            raise ValueError("verified_at must be timezone-aware.")
        secret = await self._secret_store.get(_secret_reference(owner_id))
        key = _decode_base32_secret(secret)
        if key is None:
            return False
        current_counter = int(verified_at.timestamp()) // self._time_step_seconds
        matched_counter = next(
            (
                counter
                for counter in range(
                    current_counter - self._valid_window,
                    current_counter + self._valid_window + 1,
                )
                if counter >= 0
                and hmac.compare_digest(code, _totp_code(key, counter, self._digits))
            ),
            None,
        )
        if matched_counter is None:
            return False
        async with self._lock:
            replay_key = (owner_id, matched_counter)
            if replay_key in self._used_counters:
                return False
            self._used_counters.add(replay_key)
        return True


def _secret_reference(owner_id: str) -> str:
    return f"paper-confirmation-totp:{owner_id}"


def _decode_base32_secret(secret: bytes | None) -> bytes | None:
    if not secret:
        return None
    try:
        normalized = secret.strip().upper()
        return base64.b32decode(normalized + b"=" * (-len(normalized) % 8), casefold=True)
    except (ValueError, binascii.Error):
        return None


def _totp_code(secret: bytes, counter: int, digits: int) -> str:
    digest = hmac.new(secret, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(value % (10**digits)).zfill(digits)
