"""Helpers that keep secrets out of log output.

RPC payloads and imported wallet documents used to be logged verbatim. That
leaks hot-wallet xprvs, the Bitcoin Core wallet passphrase and the SLIP77
master blinding key into ``specter.log`` - on the timeout path even at ERROR
level, so a slow node is enough to write the spending key to disk.

Everything that leaves this module is safe to log.
"""

import json
import re
from typing import Any, List

REDACTED = "<redacted>"

# RPC methods whose parameters are secrets by definition.
SENSITIVE_RPC_METHODS = frozenset(
    {
        "walletpassphrase",
        "walletpassphrasechange",
        "encryptwallet",
        "importmasterblindingkey",
        "dumpprivkey",
        "dumpprivkeys",
        "dumpwallet",
        "importwallet",
        "signmessagewithprivkey",
    }
)

# BIP32 private keys (xprv/tprv), WIF keys and SLIP77 descriptors.
_SECRET_PATTERNS = (
    re.compile(r"\b[xt]prv[1-9A-HJ-NP-Za-km-z]{20,}"),
    re.compile(r"\b[5KL][1-9A-HJ-NP-Za-km-z]{50}\b"),
    re.compile(r"slip77\([^)]*\)"),
    re.compile(r"(?i)\b(?:mnemonic|seed|password|passphrase)\b\s*[:=]\s*\S+"),
)


def redact_text(value: str) -> str:
    """Replace anything that looks like key material inside a string."""
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(REDACTED, value)
    return value


def contains_secret(value: Any) -> bool:
    """True if a value (recursively) carries key material."""
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _SECRET_PATTERNS)
    if isinstance(value, dict):
        return any(contains_secret(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_secret(item) for item in value)
    return False


def redact_value(value: Any) -> Any:
    """Deep copy with every string scrubbed."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def redact_rpc_call(method: Any, params: Any) -> dict:
    """One RPC call, reduced to what is safe to log."""
    if method in SENSITIVE_RPC_METHODS or contains_secret(params):
        return {"method": method, "params": REDACTED}
    return {"method": method, "params": redact_value(params)}


def redact_rpc_payload(payload: Any) -> List[dict]:
    """A JSON-RPC payload (single call or batch), safe to log."""
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, (list, tuple)):
        return [{"payload": REDACTED}]
    redacted = []
    for entry in payload:
        if isinstance(entry, dict):
            redacted.append(redact_rpc_call(entry.get("method"), entry.get("params")))
        else:
            redacted.append({"payload": REDACTED})
    return redacted


def redact_wallet_document(wallet_json: str) -> str:
    """Describe an imported wallet document without echoing its secrets.

    Electrum exports carry ``seed`` and ``xprv`` fields, so the document itself
    must never be logged - only its shape.
    """
    try:
        data = json.loads(wallet_json)
    except Exception:
        return "<unparsable wallet document>"
    if isinstance(data, dict):
        keys = ", ".join(sorted(str(key) for key in data.keys()))
        return f"wallet document with top-level keys: {keys}"
    if isinstance(data, list):
        return f"wallet document as a list with {len(data)} entries"
    return f"wallet document of type {type(data).__name__}"
