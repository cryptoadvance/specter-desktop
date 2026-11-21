"""Guard the legacy opt-in across the two import forms and all hot-wallet types."""

import ast
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1] / "src/cryptoadvance/specter"


def _method(path, class_name, method_name):
    module = ast.parse((ROOT / path).read_text())
    cls = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )


def _endpoint(name):
    module = ast.parse((ROOT / "server_endpoints/devices.py").read_text())
    return next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _calls_with_keyword(node, method, keyword):
    return [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and (
            call.func.attr
            if isinstance(call.func, ast.Attribute)
            else call.func.id if isinstance(call.func, ast.Name) else None
        )
        == method
        and keyword in {arg.arg for arg in call.keywords}
    ]


def test_both_import_endpoints_explicitly_forward_opt_in():
    keys = _endpoint("new_device_keys")
    manual = _endpoint("new_device_manual")
    mnemonic = _endpoint("new_device_mnemonic")
    assert len(_calls_with_keyword(keys, "add_hot_wallet_keys", "legacy")) == 2
    assert len(_calls_with_keyword(manual, "add_hot_wallet_keys", "legacy")) == 1
    assert len(_calls_with_keyword(mnemonic, "render_template", "legacy")) == 1
    for endpoint in (keys, manual, mnemonic):
        # Only an explicit checkbox value is accepted; absent/other values stay BIP39.
        comparisons = [n for n in ast.walk(endpoint) if isinstance(n, ast.Compare)]
        assert any(
            isinstance(n.comparators[0], ast.Constant)
            and n.comparators[0].value == "1"
            and "legacy_bip39" in ast.unparse(n)
            for n in comparisons
        )


def test_all_hot_wallet_types_forward_legacy_option():
    for path, name in (
        ("devices/bitcoin_core.py", "BitcoinCore"),
        ("devices/bitcoin_core.py", "BitcoinCoreWatchOnly"),
        ("devices/elements_core.py", "ElementsCore"),
    ):
        method = _method(path, name, "add_hot_wallet_keys")
        assert "legacy" in method.args.args[-1].arg
        assert ast.literal_eval(method.args.defaults[-1]) is False
        assert any(
            isinstance(n, ast.keyword) and n.arg == "legacy" for n in ast.walk(method)
        )
    elements = _method(
        "devices/elements_core.py", "ElementsCore", "add_hot_wallet_keys"
    )
    assert any(
        isinstance(n, ast.keyword)
        and n.arg == "liquid"
        and ast.literal_eval(n.value) is True
        for n in ast.walk(elements)
    )


def test_import_form_is_unchecked_and_second_step_preserves_choice():
    templates = ROOT / "templates/device"
    for name in ("new_device/new_device_mnemonic.jinja", "new_device_manual.jinja"):
        source = (templates / name).read_text()
        assert 'type="checkbox" name="legacy_bip39" value="1"' in source
        assert (
            "checked"
            not in source.split('name="legacy_bip39"', 1)[1].split("</label>", 1)[0]
        )
    source = (templates / "new_device/new_device_keys.jinja").read_text()
    form = Environment().from_string(
        source.split("{% if device_class.hot_wallet %}", 1)[1].split("{% endif %}", 1)[
            0
        ]
    )
    assert 'name="legacy_bip39" value="1"' in form.render(legacy=True)
    assert 'name="legacy_bip39" value="0"' in form.render(legacy=False)
