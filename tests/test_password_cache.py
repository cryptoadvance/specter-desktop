from types import SimpleNamespace
from unittest.mock import Mock

from cryptoadvance.specter.util.password import (
    LEGACY_PASSWORD_HASH_ITERATIONS,
    SuccessfulPasswordCache,
    hash_password,
    upgrade_password_hash,
    verify_password,
)


def user(password="correct", iterations=1000):
    return SimpleNamespace(
        id="one",
        username="alice",
        password_hash=hash_password(password, iterations=iterations),
        save_info=Mock(),
    )


def test_only_successes_are_cached_and_credentials_are_not_stored():
    cache = SuccessfulPasswordCache()
    account = user()
    check = Mock(wraps=verify_password)
    assert not cache.verify(account, "wrong", check)
    assert not cache.verify(account, "wrong", check)
    assert cache.verify(account, "correct", check)
    assert cache.verify(account, "correct", check)
    assert check.call_count == 3
    assert len(cache._entries) == 1
    assert b"correct" not in repr(cache._entries).encode()


def test_password_change_username_change_and_user_deletion_invalidate():
    cache = SuccessfulPasswordCache()
    account = user()
    check = Mock(wraps=verify_password)
    assert cache.verify(account, "correct", check)
    account.password_hash = hash_password("new", iterations=1000)
    assert not cache.verify(account, "correct", check)
    assert cache.verify(account, "new", check)
    account.username = "renamed"
    assert cache.verify(account, "new", check)
    assert check.call_count == 4
    # No account object -> no cache lookup; the API always resolves the live user.


def test_expiry_and_bounded_size(monkeypatch):
    import cryptoadvance.specter.util.password as password_module

    now = [100.0]
    monkeypatch.setattr(password_module.time, "monotonic", lambda: now[0])
    cache = SuccessfulPasswordCache(ttl=60, maxsize=1)
    account = user()
    check = Mock(wraps=verify_password)
    assert cache.verify(account, "correct", check)
    now[0] = 159.0
    assert cache.verify(account, "correct", check)
    assert check.call_count == 1
    now[0] = 161.0
    assert cache.verify(account, "correct", check)
    assert check.call_count == 2
    other = user("other")
    other.id = "two"
    assert cache.verify(other, "other", check)
    assert len(cache._entries) == 1
    assert cache.verify(account, "correct", check)
    assert check.call_count == 4


def test_legacy_upgrade_rekeys_cache_and_storage_errors_do_not_block():
    account = user(iterations=LEGACY_PASSWORD_HASH_ITERATIONS)
    cache = SuccessfulPasswordCache()
    check = Mock(wraps=verify_password)
    assert cache.verify(account, "correct", check)
    upgrade_password_hash(account, "correct")
    account.save_info.assert_called_once()
    assert account.password_hash["iterations"] > LEGACY_PASSWORD_HASH_ITERATIONS
    assert cache.verify(account, "correct", check)
    assert check.call_count == 2

    legacy = user(iterations=LEGACY_PASSWORD_HASH_ITERATIONS)
    original = legacy.password_hash
    legacy.save_info.side_effect = OSError("disk full")
    upgrade_password_hash(legacy, "correct")
    assert legacy.password_hash is original
