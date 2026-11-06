# BIP-329 label interoperability

Specter's BIP-329 support is an import/export adapter around the existing wallet
state. It does not replace the address-label store, add a per-output label
database, or change the Specter wallet backup format. The existing `labels`
object remains a mapping from a label to a list of addresses, so existing wallet
files and backups require no migration.

## Export

The separate **Download BIP-329 labels** action creates a deterministic UTF-8
JSON Lines (`.jsonl`) file containing:

- `addr` records for explicitly stored address labels. Generated display names
  such as `Address #4` and `Change #8` are excluded.
- `output` records for current known wallet UTXOs whose address has an explicit
  label. The output label is derived from that address label.
- `spendable:false` on current outputs in Specter's frozen UTXO list. A frozen
  unlabeled output is exported without inventing a `label` value.

Specter does not fabricate `tx` records from its address-derived transaction
display labels. It also omits `spendable:true`; omission is the minimal BIP-329
representation for outputs that are not frozen.

Label exports contain privacy-sensitive addresses, transaction outpoints, and
descriptions. Keep them private and delete unencrypted copies when no longer
needed.

## Why export and import are intentionally asymmetric

Specter stores an explicit label on an address but also uses that label as the
effective label shown for the address's UTXOs. BIP-329 can represent address and
output labels independently. Sparrow also imports `addr` and `output` records
independently and does not propagate an imported address label to its outputs.

An `addr`-only export would therefore preserve Specter's stored label but lose
the UTXO-label semantics users see and use for coin control after migration.
The adapter materializes the same explicit address label on each current known
output for that address. These output records preserve existing semantics for a
wallet with a richer label model; they do not mean that Specter stores
independent per-output labels.

The reverse conversion is unsafe. An external wallet may assign different
labels to outputs on a reused address, including spent historical outputs.
Collapsing them into one Specter address label could destroy information and
change the apparent labels of other transactions.

For example, even if ten current UTXOs on the same address all contain
`output.label = "Alice"`, Specter does not infer the address label `Alice`.
Agreement among current UTXOs does not prove that spent historical outputs on
that reused address had the same meaning. The file must contain an explicit
`addr` record to update the Specter address label. Any `spendable` value on the
ten output records is still processed independently for each known outpoint.

This implementation keeps that adapter boundary. The underlying
address/transaction-label coupling is tracked in
[issue #2018](https://github.com/cryptoadvance/specter-desktop/issues/2018).
A long-term redesign could store address, transaction, and output labels
independently; lossless BIP-329 output-label import would require that additional
output-label storage beyond the transaction-label change proposed there.

## Import, conflicts, and frozen state

An `addr` record for an address in the selected wallet updates that address
through Specter's existing label mechanism. Unknown addresses and outpoints do
not create wallet state. Unknown record types and optional fields are ignored
for forward compatibility.

The optional `origin` descriptor is type-checked as a string but is neither
parsed nor used for wallet selection. Specter does not import the transaction
labels for which BIP-329 primarily defines origin disambiguation, and
address/output records
must already resolve to the selected wallet. Records with different labels for
the same reference remain conflicting even if their origins differ; Specter
does not guess which origin should win.

Imported `output.label` values are reported as unsupported rather than written
to the address store. Conflicting duplicate address or `spendable` records are
skipped instead of being resolved by file order. Malformed records are validated
atomically and skipped without creating partial state. The UI reports ignored,
unsupported, malformed, conflicting, and failed records without logging label
or outpoint contents.

For a known output, `spendable:false` freezes it and `spendable:true` unfreezes
it through Specter's existing frozen-UTXO mechanism. The wallet refreshes its
UTXO set before importing or exporting output state.

Frozen-state updates reconcile Specter's persisted ownership marker with
Bitcoin Core's current lock state. The operation is idempotent, repairs a
missing non-persistent Core lock for an existing Specter freeze, and does not
record a successful update unless the required Core operation and verified
wallet JSON write succeed. Storage callbacks and balance refreshes run only
after that write; their failure does not roll back or misreport the persisted
frozen state. A wallet-write failure restores the prior in-memory and persisted
state and independently attempts to restore Core's prior lock state.

A wallet-specific reentrant lock serializes the complete pending-PSBT read,
Core RPC, RAM update, and wallet-write sequence. Pending-PSBT save/delete and
the legacy UI freeze toggle use the same lock, so their Core-lock ownership
transitions cannot interleave. Every wallet JSON snapshot and write also takes
this lock, so an older concurrent save cannot overwrite a newer ownership
state. Deleting a pending PSBT does not unlock an input that remains protected
by a Specter freeze or another pending PSBT.

Outputs used by pending PSBTs are never frozen or unfrozen by this importer.
A Core lock without a matching Specter frozen marker is protected in the same
way. Such requests are reported as conflicts.

Bitcoin Core does not record an owner for `lockunspent` locks. If Specter has a
persisted frozen marker for an outpoint, its original Core lock disappears, and
another process later locks the same outpoint, the two locks are
indistinguishable. The importer treats the persisted marker as ownership in
that case. Pending PSBT inputs remain protected independently of this marker.

## References

The implementation follows the current
[BIP-329 specification](https://github.com/bitcoin/bips/blob/master/bip-0329.mediawiki).
Sparrow compatibility was checked against commit `3dc99b6` of its
[`WalletLabels.java`](https://github.com/sparrowwallet/sparrow/blob/3dc99b6b54a6c7a43071aa9e8852c8b2e813b6d1/src/main/java/com/sparrowwallet/sparrow/io/WalletLabels.java).
That implementation reads UTF-8 JSON Lines, distinguishes `addr` and `output`
labels, identifies outputs by `txid:vout`, accepts `spendable` without a label,
and maps the boolean value to its frozen status.
