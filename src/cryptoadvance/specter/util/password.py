"""Password hashing for the Specter login.

Kept in its own module so the KDF parameters are testable without pulling in
the whole Specter stack. Hashes created before the iteration bump still verify
and are upgraded on the next successful login.
"""

import binascii
import hashlib
import hmac
import os

# OWASP recommends 600k iterations for PBKDF2-HMAC-SHA256 (2023 guidance).
PASSWORD_HASH_ITERATIONS = 600000
# Hashes created before this change used 10k iterations.
LEGACY_PASSWORD_HASH_ITERATIONS = 10000


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
