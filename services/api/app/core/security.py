"""Passwords and session tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Argon2id with the library's current recommended parameters (RFC 9106 low-memory profile).
_hasher = PasswordHasher()

# Verified against when an email doesn't exist, so a wrong email takes as long as a wrong
# password and response times don't reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash("tindawise-timing-equalizer")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> str:
    """256 bits of randomness, URL-safe. Shown to the client once; only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
