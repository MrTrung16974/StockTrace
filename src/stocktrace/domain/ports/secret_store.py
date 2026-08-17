"""Port for encrypted broker credentials, kept outside account-link metadata."""

from __future__ import annotations

from typing import Protocol


class SecretStore(Protocol):
    """Persist secret bytes by opaque reference; implementations must encrypt at rest."""

    async def put(self, secret_reference: str, secret: bytes) -> None:
        """Encrypt and store one secret value."""
        ...

    async def get(self, secret_reference: str) -> bytes | None:
        """Return decrypted secret bytes only to an authorized application service."""
        ...

    async def revoke(self, secret_reference: str) -> None:
        """Make a secret irretrievable by its opaque reference."""
        ...
