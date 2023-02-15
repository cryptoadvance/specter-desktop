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


def test_last_lines(caplog):
    from cryptoadvance.specter.util.shell import get_last_lines_from_file

    lines = get_last_lines_from_file("LICENSE", 30)
    assert lines[-2].startswith("OUT OF OR IN CONNECTION WITH THE SOFTWARE ")


def test_grep():
    from cryptoadvance.specter.util.shell import grep

    assert grep("./pyproject.toml", 'name = "cryptoadvance.specter"')
