"""Provision synthetic bearer identities and compare hashes without exposing raw tokens."""

import hmac
import json
import secrets
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, ValidationError, field_validator

from veritycx.conversations.models import ClosedModel, VersionedModel, canonical_uuid, parse_json


class AuthError(ValueError):
    """Report a safe credential category without token or owner details."""


class DemoPrincipal(ClosedModel):
    """Hold only the server-assigned owner and a high-entropy credential digest."""

    owner_id: str
    token_digest: str = Field(pattern=r"^[0-9a-f]{64}$", repr=False)
    enabled: bool

    @field_validator("owner_id")
    @classmethod
    def valid_owner(cls, value: str) -> str:
        """Require canonical UUID owners before authorizing a request."""
        return canonical_uuid(value)


class PrincipalFile(VersionedModel):
    """Validate the bounded local identity configuration without dynamic fields."""

    principals: list[DemoPrincipal] = Field(min_length=1, max_length=1000)


def load_principals(path: Path) -> tuple[DemoPrincipal, ...]:
    """Read a bounded strict credential file; malformed configuration fails closed."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("too_large")
        values = PrincipalFile.model_validate(parse_json(raw)).principals
        if len({p.token_digest for p in values}) != len(values):
            raise ValueError("duplicate_digest")
        return tuple(values)
    except (OSError, ValueError, ValidationError):
        raise AuthError("invalid_auth_configuration") from None


def authenticate(header: str | None, principals: tuple[DemoPrincipal, ...]) -> UUID:
    """Resolve a bearer token through constant-time digest comparisons, never caller identity."""
    if header is None or not header.startswith("Bearer ") or len(header) > 512:
        raise AuthError("unauthorized")
    token = header[7:]
    if len(token) < 43 or not token.isascii():
        raise AuthError("unauthorized")
    digest = sha256(token.encode("ascii")).hexdigest()
    matched: str | None = None
    # Compare every configured digest; a matching first row must not short-circuit the scan.
    for principal in principals:
        equal = hmac.compare_digest(digest, principal.token_digest)
        if equal and principal.enabled:
            matched = principal.owner_id
    if matched is None:
        raise AuthError("unauthorized")
    return UUID(matched)


def init_demo(directory: Path) -> tuple[Path, Path, Path]:
    """Issue two 256-bit tokens into new local files, refusing every existing target."""
    directory.mkdir(parents=True, exist_ok=True)
    targets = (directory / "auth.json", directory / "client-1.token", directory / "client-2.token")
    lock = directory / ".auth-init-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise AuthError("credential_exists") from None
    try:
        if any(target.exists() or target.is_symlink() for target in targets):
            raise AuthError("credential_exists")
        tokens = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
        principals = [
            DemoPrincipal(
                owner_id=str(uuid4()), enabled=True, token_digest=sha256(token.encode()).hexdigest()
            )
            for token in tokens
        ]
        # Exclusive creates also protect against races with unrelated local writers.
        for path, value in zip(targets[1:], tokens, strict=True):
            with path.open("x", encoding="utf-8") as stream:
                stream.write(value + "\n")
        with targets[0].open("x", encoding="utf-8") as stream:
            json.dump(PrincipalFile(principals=principals).model_dump(), stream)
        return targets
    except FileExistsError:
        raise AuthError("credential_exists") from None
    finally:
        lock.rmdir()
