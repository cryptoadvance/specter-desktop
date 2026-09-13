"""BIP-329 JSON Lines parsing and serialization helpers.

BIP-329 is an interoperability format only.  Specter's canonical label storage
remains the address list and its legacy ``{label: [addresses]}`` export.
"""

import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


BIP329_TYPES = {"tx", "addr", "pubkey", "input", "output", "xpub", "spscan"}
MAX_BIP329_FILE_SIZE = 10 * 1024 * 1024
MAX_BIP329_LINE_SIZE = 1024 * 1024
OUTPOINT_RE = re.compile(r"^(?P<txid>[0-9a-fA-F]{64}):(?P<vout>0|[1-9][0-9]*)$")


@dataclass
class BIP329ImportResult:
    """Non-sensitive summary of a BIP-329 import."""

    imported_address_labels: int = 0
    updated_frozen_utxos: int = 0
    ignored_records: int = 0
    unsupported_output_labels: int = 0
    malformed_records: int = 0
    conflicting_records: int = 0
    failed_records: int = 0
    is_bip329: bool = True

    @property
    def has_warnings(self) -> bool:
        return bool(
            self.ignored_records
            or self.unsupported_output_labels
            or self.malformed_records
            or self.conflicting_records
            or self.failed_records
        )


def normalize_outpoint(ref: str) -> Optional[str]:
    """Return a canonical BIP-329 output reference, or ``None`` if invalid."""

    if not isinstance(ref, str):
        return None
    match = OUTPOINT_RE.fullmatch(ref)
    if not match:
        return None
    vout = int(match.group("vout"))
    if vout > 0xFFFFFFFF:
        return None
    return f"{match.group('txid').lower()}:{vout}"


def parse_bip329_jsonl(
    value: str,
) -> Tuple[Optional[List[Dict]], BIP329ImportResult]:
    """Parse BIP-329 records when ``value`` looks like BIP-329 JSONL.

    ``None`` records means that the input is not BIP-329 and should be offered
    to Specter's legacy importers. Invalid lines in an otherwise recognizable
    BIP-329 document are counted and skipped, as JSON Lines is intended to
    contain failures to individual records.
    """

    result = BIP329ImportResult()
    if not isinstance(value, str):
        return None, result
    encoded_size = len(value.encode("utf-8"))

    records = []
    detected = False
    for line in value.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            result.malformed_records += 1
            continue

        # A string type/ref pair is the common BIP-329 record envelope. Detect
        # unknown future types as BIP-329 too so they can be ignored as required
        # by the specification. Requiring both fields avoids diverting legacy
        # JSON objects merely because they contain a key named "type".
        if (
            isinstance(record, dict)
            and isinstance(record.get("type"), str)
            and isinstance(record.get("ref"), str)
        ):
            detected = True
            # Apply the BIP-329 safety limit only after detecting BIP-329.
            # Legacy Specter, Electrum and CSV imports had no such limit.
            if encoded_size > MAX_BIP329_FILE_SIZE:
                raise ValueError("BIP-329 label file is too large")
            if len(line.encode("utf-8")) > MAX_BIP329_LINE_SIZE:
                result.malformed_records += 1
                continue
        if not isinstance(record, dict):
            result.malformed_records += 1
            continue
        if not isinstance(record.get("type"), str) or not isinstance(
            record.get("ref"), str
        ):
            result.malformed_records += 1
            continue
        records.append(record)

    if not detected:
        return None, BIP329ImportResult(is_bip329=False)
    return records, result


def serialize_bip329_records(records: Iterable[Dict]) -> str:
    """Serialize records as deterministic UTF-8-safe JSON Lines."""

    lines = [
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    ]
    return "\n".join(lines) + ("\n" if lines else "")
