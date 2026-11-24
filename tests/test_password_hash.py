"""Tests for the login password KDF.

Legacy hashes (10k iterations, no ``iterations`` field) must keep verifying so
existing users are not locked out; new hashes use the current iteration count
and old ones are flagged for an upgrade on the next login.
"""

from cryptoadvance.specter.util.password import (
    LEGACY_PASSWORD_HASH_ITERATIONS,
    PASSWORD_HASH_ITERATIONS,
    hash_password,
    password_hash_needs_rehash,
    upgrade_password_hash,
    verify_password,
)
from types import SimpleNamespace
from unittest.mock import Mock

PASSWORD = "correct horse battery staple"


def test_new_hash_uses_current_iteration_count():
    stored = hash_password(PASSWORD)
    assert stored["iterations"] == PASSWORD_HASH_ITERATIONS
    assert PASSWORD_HASH_ITERATIONS >= 600000
    assert "salt" in stored and "pwdhash" in stored


def test_new_hash_roundtrip():
    stored = hash_password(PASSWORD)
    assert verify_password(stored, PASSWORD)
    assert not verify_password(stored, PASSWORD + "x")


def test_legacy_hash_still_verifies():
    legacy = hash_password(PASSWORD, iterations=LEGACY_PASSWORD_HASH_ITERATIONS)
    # hashes written by older versions have no "iterations" field at all
    legacy.pop("iterations")
    assert verify_password(legacy, PASSWORD)
    assert not verify_password(legacy, "wrong password")


def test_needs_rehash_flags_legacy_hashes_only():
    legacy = hash_password(PASSWORD, iterations=LEGACY_PASSWORD_HASH_ITERATIONS)
    legacy.pop("iterations")
    assert password_hash_needs_rehash(legacy)
    assert not password_hash_needs_rehash(hash_password(PASSWORD))


def test_salt_is_unique_per_hash():
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)
    assert first["salt"] != second["salt"]
    assert first["pwdhash"] != second["pwdhash"]


def test_upgrade_persists_legacy_hash_and_restores_it_on_storage_error():
    previous = hash_password(PASSWORD, iterations=LEGACY_PASSWORD_HASH_ITERATIONS)
    previous.pop("iterations")
    user = SimpleNamespace(username="alice", password_hash=previous, save_info=Mock())
    upgrade_password_hash(user, PASSWORD)
    user.save_info.assert_called_once()
    assert user.password_hash["iterations"] == PASSWORD_HASH_ITERATIONS
    assert verify_password(user.password_hash, PASSWORD)

    user.password_hash = previous
    user.save_info.side_effect = OSError("disk full")
    upgrade_password_hash(user, PASSWORD)
    assert user.password_hash is previous
