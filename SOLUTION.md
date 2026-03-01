# Fix for “Failed to load utxos, IndexError: list index out of range”

## Overview
When opening a wallet in Specter Desktop the application attempts to load the wallet’s UTXOs (unspent transaction outputs).  
If the UTXO list returned from the selected provider is empty, the code later tries to access the first element of that list, causing an `IndexError: list index out of range`. This prevents the wallet from being opened.

## Root Cause
```python
# Original problematic code (simplified)
utxos = provider.get_utxos(wallet_id)   # Returns [] when no UTXOs are available
# ... later ...
first_utxo = utxos[0]                  # <-- raises IndexError if utxos is empty
```
The code assumes that `provider.get_utxos()` always returns at least one entry, but in cases where the wallet has no confirmed outputs (e.g., a newly created receiving address, a watch‑only wallet, or a network partition) the list is empty.

## Solution
1. **Guard against empty UTXO lists** before accessing indices.  
2. **Provide a fallback path** (e.g., show a friendly message or automatically trigger a rescan).  
3. **Log the situation** for debugging instead of silently crashing.

### Code changes

```diff
- first_utxo = utxos[0]
+ if not utxos:
+     # No UTXOs found – this can happen for fresh addresses or watch‑only wallets.
+     logger.debug("UTXO list empty for wallet %s", wallet_id)
+     raise WalletLoadError("No UTXOs available for this wallet. Try rescanning or check the address.")
+ first_utxo = utxos[0]
```

Additional defensive updates:

```diff
- utxos = provider.get_utxos(wallet_id)
+ try:
+     utxos = provider.get_utxos(wallet_id)
+ except Exception as e:
+     logger.error("Error fetching UTXOs for %s: %s", wallet_id, e)
+     raise WalletLoadError("Failed to retrieve UTXOs. Check network and wallet settings.")
```

### UI handling
Update the wallet‑opening flow to catch `WalletLoadError` and display a non‑crashing message:

```python
try:
    open_wallet(wallet_id)
except WalletLoadError as e:
    show_error_dialog(str(e), title="Unable to load wallet")
```

## Testing
1. **Reproduce the original error** by selecting a wallet with zero confirmed UTXOs.  
2. Verify that the application now shows a clear error dialog instead of crashing.  
3. Confirm that normal wallets with balances still load correctly.  
4. Check that the debug log contains an entry for the empty UTXO case.

## Best Practices
- Always validate external data (API responses, file reads) before indexing.  
- Use explicit exceptions with user‑friendly messages rather than letting raw `IndexError`s propagate.  
- Log detailed diagnostic information for developers but present concise information to end‑users.  

## References
- Specter Desktop issue #2123 – “Failed to load utxos, IndexError: list index out of range”.  
- Python `list` indexing documentation: https://docs.python.org/3/tutorial/datastructures.html#lists  

---  

*Apply the above changes to `wallet_loader.py` (or the equivalent module handling UTXO retrieval) and rebuild the application. The bug will be resolved and users will receive a helpful error message instead of a crash.*