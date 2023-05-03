from embit.bip32 import parse_path


def is_testnet(derivation_path):
    """Returns true if m/xyz/1'/... is 1 at the bip32 relevant position"""
    without_master_maybe_fp = "/".join(derivation_path.split("/")[1:])
    parsed_array = parse_path(without_master_maybe_fp)
    return parsed_array[1] == 1 or parsed_array[1] - 0x80000000 == 1
