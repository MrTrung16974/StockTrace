"""Encrypted in-memory SecretStore for tests and local development only."""

from __future__ import annotations

import asyncio

from cryptography.fernet import Fernet, InvalidToken


class SecretStoreIntegrityError(RuntimeError):
    """Raised when encrypted credential material cannot be authenticated/decrypted."""


class EncryptedInMemorySecretStore:
    """Fernet-encrypted transient store; never use this adapter for production secrets."""

    def __init__(self, encryption_key: bytes) -> None:
        self._fernet = Fernet(encryption_key)
        self._ciphertexts: dict[str, bytes] = {}
        self._lock = asyncio.Lock()

    async def put(self, secret_reference: str, secret: bytes) -> None:
        """Encrypt and hold a credential without retaining plaintext in storage."""
        if not secret_reference.strip():
            raise ValueError("secret_reference must not be empty.")
        if not secret:
            raise ValueError("secret must not be empty.")
        async with self._lock:
            self._ciphertexts[secret_reference] = self._fernet.encrypt(secret)

    async def get(self, secret_reference: str) -> bytes | None:
        """Decrypt a credential only for the caller holding its opaque reference."""
        async with self._lock:
            ciphertext = self._ciphertexts.get(secret_reference)
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise SecretStoreIntegrityError("encrypted secret cannot be authenticated.") from exc

    async def revoke(self, secret_reference: str) -> None:
        """Remove encrypted material so it cannot later be retrieved."""
        async with self._lock:
            self._ciphertexts.pop(secret_reference, None)
