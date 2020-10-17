import logging


def test_which(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    import cryptoadvance.specter.util.shell as helpers

    try:
        helpers.which("some_non_existing_binary")
        assert False, "Should raise an Exception"
    except:
        pass
    assert (
        helpers.which("date") == "/bin/date" or helpers.which("date") == "/usr/bin/date"
    )  # travis-CI has it on /bin/date
