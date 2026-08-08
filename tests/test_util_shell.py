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


def test_grep(tmp_path):
    """grep returns a (found, line)-tuple. Asserting on the tuple itself is
    always truthy, so always assert on the first element!"""
    from cryptoadvance.specter.util.shell import grep

    some_file = tmp_path / "some_file.txt"
    some_file.write_text('name = "cryptoadvance_specter"\nversion = "1.2.3"\n')

    found, line = grep(str(some_file), 'name = "cryptoadvance_specter"')
    assert found
    assert line.strip() == 'name = "cryptoadvance_specter"'

    found, line = grep(str(some_file), "does not exist")
    assert not found
    assert line is None
