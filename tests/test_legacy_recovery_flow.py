"""Guard the explicit legacy BIP39 opt-in across both import forms and all hot-wallet types.

The NFKD (BIP39) derivation is the default. Legacy derivation is only ever
reached through an explicit checkbox whose value must be the literal "1", and
that choice must survive every step of the import flow.
"""

import ast
from pathlib import Path

from jinja2 import Environment

from cryptoadvance.specter.util.mnemonic import legacy_bip39_requested

ROOT = Path(__file__).resolve().parents[1] / "src/cryptoadvance/specter"
TEMPLATES = ROOT / "templates/device"


def _tree(path):
    return ast.parse((ROOT / path).read_text())


def _endpoint(name):
    return next(
        node
        for node in _tree("server_endpoints/devices.py").body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _class_method(path, class_name, method_name):
    module = _tree(path)
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


def _calls(node, name):
    calls = []
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if isinstance(func, ast.Attribute):
            func_name = func.attr
        elif isinstance(func, ast.Name):
            func_name = func.id
        else:
            continue
        if func_name == name:
            calls.append(call)
    return calls


def _keywords(call):
    return {kw.arg for kw in call.keywords if kw.arg is not None}


def _render(source, **context):
    env = Environment()
    env.globals["_"] = lambda message: message
    return env.from_string(source).render(**context)


def _checkbox_block(source):
    start = source.index('<label><input type="checkbox" name="legacy_bip39"')
    end = source.index("</label>", start)
    return source[start:end]


def test_legacy_opt_in_requires_the_literal_checkbox_value():
    """No silent fallback: anything but "1" keeps the BIP39 default."""
    assert legacy_bip39_requested({"legacy_bip39": "1"}) is True
    assert legacy_bip39_requested({}) is False
    for value in (None, "", "0", "true", "on", "yes", "1 ", "01"):
        form = {} if value is None else {"legacy_bip39": value}
        assert legacy_bip39_requested(form) is False


def test_import_endpoints_route_the_opt_in_through_the_helper():
    keys = _endpoint("new_device_keys")
    mnemonic = _endpoint("new_device_mnemonic")
    manual = _endpoint("new_device_manual")
    for endpoint in (keys, mnemonic, manual):
        reads = [
            call
            for call in ast.walk(endpoint)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "legacy_bip39_requested"
        ]
        assert len(reads) == 1
        # The raw form key is never interpreted by the endpoint itself, so a
        # stray value cannot enable legacy derivation.
        string_constants = {
            node.value
            for node in ast.walk(endpoint)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "legacy_bip39" not in string_constants

    # new_device_keys: both the "add keys" and the "create device" branches.
    add_calls = _calls(keys, "add_hot_wallet_keys")
    assert len(add_calls) == 2
    for call in add_calls:
        assert "legacy" in _keywords(call)
    # The re-rendered form keeps the choice for the next step.
    form_renders = [
        call
        for call in _calls(keys, "render_template")
        if isinstance(call.args[0], ast.Name)
    ]
    assert len(form_renders) == 1
    assert "legacy" in _keywords(form_renders[0])

    # new_device_mnemonic: forwards the choice into the keys step template.
    step_two = [
        call
        for call in _calls(mnemonic, "render_template")
        if "new_device_keys.jinja" in ast.unparse(call.args[0])
    ]
    assert len(step_two) == 1
    assert "legacy" in _keywords(step_two[0])

    # new_device_manual: forwards into the hot wallet import.
    manual_calls = _calls(manual, "add_hot_wallet_keys")
    assert len(manual_calls) == 1
    assert "legacy" in _keywords(manual_calls[0])


def test_all_hot_wallet_classes_accept_and_forward_the_opt_in():
    for path, class_name in (
        ("devices/bitcoin_core.py", "BitcoinCore"),
        ("devices/bitcoin_core.py", "BitcoinCoreWatchOnly"),
        ("devices/elements_core.py", "ElementsCore"),
    ):
        method = _class_method(path, class_name, "add_hot_wallet_keys")
        assert method.args.args[-1].arg == "legacy"
        assert ast.literal_eval(method.args.defaults[-1]) is False
        keywords = {kw.arg for kw in ast.walk(method) if isinstance(kw, ast.keyword)}
        assert "legacy" in keywords

    # BitcoinCore derives the root key from the forwarded flag.
    bitcoin = _class_method(
        "devices/bitcoin_core.py", "BitcoinCore", "add_hot_wallet_keys"
    )
    root_calls = _calls(bitcoin, "mnemonic_to_root")
    assert len(root_calls) == 1
    assert _keywords(root_calls[0]) == {"legacy"}

    # ElementsCore derives the blinding key from the same flag and keeps the
    # legacy Liquid wordlist distinction.
    elements = _class_method(
        "devices/elements_core.py", "ElementsCore", "add_hot_wallet_keys"
    )
    seed_calls = _calls(elements, "mnemonic_to_seed")
    assert len(seed_calls) == 1
    assert _keywords(seed_calls[0]) == {"legacy", "liquid"}
    liquid_kw = next(kw for kw in seed_calls[0].keywords if kw.arg == "liquid")
    assert ast.literal_eval(liquid_kw.value) is True


def test_both_import_forms_offer_an_unchecked_legacy_opt_in():
    for name in (
        "new_device/new_device_mnemonic.jinja",
        "new_device_manual.jinja",
    ):
        source = (TEMPLATES / name).read_text()
        block = _checkbox_block(source)
        assert 'value="1"' in block
        rendered = _render(block)
        assert 'value="1"' in rendered
        assert "checked" not in rendered
        # A validation-error re-render must not silently drop the opt-in.
        assert "checked" in _render(block, legacy=True)


def test_second_import_step_preserves_the_choice():
    source = (TEMPLATES / "new_device/new_device_keys.jinja").read_text()
    start = source.index("{% if device_class.hot_wallet %}")
    end = source.index("\n        {% endif %}", start)
    block = source[start:end]
    hidden = [line for line in block.splitlines() if 'name="legacy_bip39"' in line]
    assert len(hidden) == 1
    line = hidden[0]
    assert 'value="1"' in _render(line, legacy=True)
    assert 'value="0"' in _render(line, legacy=False)
    # Unset (e.g. "add keys" on an existing device) stays on the default.
    assert 'value="0"' in _render(line)


def test_derivation_change_is_warned_about_in_the_ui():
    mnemonic_form = (TEMPLATES / "new_device/new_device_mnemonic.jinja").read_text()
    assert "Non-ASCII passphrases are normalized for BIP39" in mnemonic_form
    assert "no Unicode normalization" in mnemonic_form
    keys_form = (TEMPLATES / "new_device/new_device_keys.jinja").read_text()
    assert "Legacy BIP39 derivation is enabled for this import" in keys_form
