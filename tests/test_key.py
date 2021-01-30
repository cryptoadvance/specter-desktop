from cryptoadvance.specter.key import Key


### Testing for the major attributes of the Key class using its classmethod
### parse_xpub which in turn uses base58 de- and encoding functions from embit


def test_fingerprint(ghost_machine_xpub_44):
    key = Key.parse_xpub(ghost_machine_xpub_44)
    assert key.fingerprint == "81f802e3"


def test_key_type(ghost_machine_ypub):
    key = Key.parse_xpub(ghost_machine_ypub)
    assert key.key_type == "sh-wpkh"


def test_purpose(ghost_machine_ypub):
    key = Key.parse_xpub(ghost_machine_ypub)
    assert key.purpose == "Single (Nested)"


def test_xpub(ghost_machine_ypub, ghost_machine_xpub_49):
    key = Key.parse_xpub(ghost_machine_ypub)
    assert key.xpub == ghost_machine_xpub_49


def test_derivation(ghost_machine_zpub):
    key = Key.parse_xpub(f"[81f802e3/84'/0'/3]{ghost_machine_zpub}")
    assert key.derivation == "m/84h/0h/3"
