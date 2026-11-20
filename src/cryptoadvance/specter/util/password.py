"""Password hashing for the Specter login.

Kept in its own module so the KDF parameters are testable without pulling in
the whole Specter stack. Hashes created before the iteration bump still verify
and are upgraded on the next successful login.
"""

import binascii
import hashlib
import hmac
import os
import logging
import secrets
import time
from collections import OrderedDict
from threading import Lock

# OWASP recommends 600k iterations for PBKDF2-HMAC-SHA256 (2023 guidance).
PASSWORD_HASH_ITERATIONS = 600000
# Hashes created before this change used 10k iterations.
LEGACY_PASSWORD_HASH_ITERATIONS = 10000
logger = logging.getLogger(__name__)


def hash_password(plaintext_password, iterations: int = PASSWORD_HASH_ITERATIONS):
    """Hash a password for storing."""
    salt = binascii.b2a_base64(hashlib.sha256(os.urandom(60)).digest()).strip()
    pwdhash = (
        binascii.b2a_base64(
            hashlib.pbkdf2_hmac(
                "sha256", plaintext_password.encode("utf-8"), salt, iterations
            )
        )
        .strip()
        .decode()
    )
    return {"salt": salt.decode(), "pwdhash": pwdhash, "iterations": iterations}


def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    iterations = stored_password.get("iterations", LEGACY_PASSWORD_HASH_ITERATIONS)
    pwdhash = hashlib.pbkdf2_hmac(
        "sha256",
        provided_password.encode("utf-8"),
        stored_password["salt"].encode(),
        iterations,
    )
    return hmac.compare_digest(pwdhash, binascii.a2b_base64(stored_password["pwdhash"]))


def password_hash_needs_rehash(stored_password) -> bool:
    """True for hashes created with an outdated iteration count."""
    iterations = stored_password.get("iterations", LEGACY_PASSWORD_HASH_ITERATIONS)
    return iterations < PASSWORD_HASH_ITERATIONS


def upgrade_password_hash(user, password):
    """Persist a stronger login hash after successful authentication only."""
    if not password_hash_needs_rehash(user.password_hash):
        return
    previous_hash = user.password_hash
    user.password_hash = hash_password(password)
    try:
        user.save_info()
    except OSError as e:  # a storage failure must not prevent a valid login
        user.password_hash = previous_hash
        logger.warning("Could not upgrade password hash for %s: %s", user.username, e)


class SuccessfulPasswordCache:
    """Bounded, process-local cache for successful Basic authentication only.

    The stored hash is part of the key, so password changes (and user reloads)
    invalidate an entry without coordinating across workers. Never store a
    plaintext password or an unsalted password digest.
    """

    def __init__(self, ttl=60, maxsize=128):
        self.ttl = ttl
        self.maxsize = maxsize
        self._secret = secrets.token_bytes(32)
        self._entries = OrderedDict()
        self._lock = Lock()

    def verify(self, user, password, verifier=verify_password):
        stored = user.password_hash
        username = user.username.encode("utf-8")
        credential = hmac.new(
            self._secret,
            len(username).to_bytes(4, "big") + username + password.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        key = (
            user.id,
            stored["salt"],
            stored["pwdhash"],
            stored.get("iterations", LEGACY_PASSWORD_HASH_ITERATIONS),
            credential,
        )
        now = time.monotonic()
        with self._lock:
            expiry = self._entries.get(key)
            if expiry is not None and expiry > now:
                self._entries.move_to_end(key)
                return True
            self._entries.pop(key, None)

        if not verifier(stored, password):
            return False

        # A concurrent password change must not populate a cache entry for
        # credentials that no longer authenticate.
        with self._lock:
            if user.password_hash is stored:
                self._entries[key] = time.monotonic() + self.ttl
                self._entries.move_to_end(key)
                if len(self._entries) > self.maxsize:
                    self._entries.popitem(last=False)
        return True
