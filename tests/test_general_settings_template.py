"""Test that general_settings.jinja handles optional extensions safely.

Regression test for #2498: spectrum_endpoint.wallets_get crashes
when the Spectrum extension is not installed.
"""

import re
from pathlib import Path


TEMPLATE_PATH = Path(__file__).parent.parent / (
    "src/cryptoadvance/specter/templates/settings/general_settings.jinja"
)


def test_spectrum_wallets_get_is_guarded():
    """The spectrum_endpoint.wallets_get url_for must be inside a conditional
    that checks whether the spectrum extension is loaded."""
    content = TEMPLATE_PATH.read_text()

    # Find all occurrences of spectrum_endpoint
    matches = list(re.finditer(r"spectrum_endpoint", content))
    assert len(matches) > 0, "Template should reference spectrum_endpoint"

    for match in matches:
        # Get the surrounding context (500 chars before the match)
        start = max(0, match.start() - 500)
        before = content[start : match.start()]

        # There must be a guard check before the url_for call
        # Either {% if "spectrum" in ... %} or similar conditional
        assert re.search(
            r'{%[-\s]+if\s+.*spectrum.*service_manager', before
        ), (
            f"spectrum_endpoint reference at position {match.start()} "
            f"is not guarded by a service_manager check. "
            f"This will crash when Spectrum extension is not installed."
        )


def test_spectrum_guard_has_matching_endif():
    """The spectrum conditional block must be properly closed."""
    content = TEMPLATE_PATH.read_text()

    # Find the guard
    guard_match = re.search(
        r'{%[-\s]+if\s+"spectrum"\s+in\s+specter\.service_manager\.services\s*%}',
        content,
    )
    assert guard_match is not None, "Expected spectrum guard conditional"

    # Find the matching endif after the guard
    after_guard = content[guard_match.end() :]
    assert "{% endif %}" in after_guard, "spectrum guard must have matching endif"

    # The endif should come before the next major section
    endif_pos = after_guard.index("{% endif %}")
    # And the spectrum_endpoint reference should be between the if and endif
    assert "spectrum_endpoint" in after_guard[:endif_pos], (
        "spectrum_endpoint.wallets_get should be inside the guarded block"
    )
