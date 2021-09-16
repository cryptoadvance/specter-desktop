from embit.liquid.pset import PSET


def to_canonical_pset(pset):
    """
    Removes unblinded information from the transaction
    so Elements Core can decode it
    """
    # if we got psbt, not pset - just return
    if not pset.startswith("cHNl"):
        return pset
    tx = PSET.from_string(pset)

    for inp in tx.inputs:
        inp.value = None
        inp.asset = None
        inp.value_blinding_factor = None
        inp.asset_blinding_factor = None

    for out in tx.outputs:
        if out.is_blinded:
            out.asset = None
            out.asset_blinding_factor = None
            out.value = None
            out.value_blinding_factor = None
    return str(tx)
