from cryptoadvance.specter.util.psbt import SpecterPSBT, Descriptor

PSBT = "cHNidP8BAH0CAAAAAZ3WUGbo+qq+uhku8ZGlccpVnEUe7DpXc2WT8eFBOY5NAAAAAAD9////AoCWmAAAAAAAFgAUknv5/4QLPO9YhpvFXh8Yd1A2uiloP10FAAAAACJRIBTYMq2X8Wb48epOTevfvMFFs1Rywret7quv2PDmQ27QAAAAAAABASsA4fUFAAAAACJRIGGkhZUFZ4wSdPRYh8+NH8rT4OPZ96DG+4g40XzsrkswIRbrOsC4g4bRFEv7o2eV6PjsmXRITNcywDkjoKE3IXZEcBkAc8XaClYAAIABAACAAAAAgAAAAAAAAAAAARcg6zrAuIOG0RRL+6Nnlej47Jl0SEzXMsA5I6ChNyF2RHAAAAEFIPF/TUgvecmr7Omn2RaD3/WuEWxZkvyKAVX8FtRQMndaIQfxf01IL3nJq+zpp9kWg9/1rhFsWZL8igFV/BbUUDJ3WhkAc8XaClYAAIABAACAAAAAgAEAAAABAAAAAA=="
DESC = "tr([73c5da0a/86h/1h/0h]tprv8h5RpVZ1VP6ZenvqJAuUYCenQqYgRjsAMjqnVY54FqQzk52jqP12mPHa77wXQm9WeJSRjDhT3N5RL2Ye93Z4kR6rWTNo25Tdq6UfopDczBZ/{0,1}/*)"


def test_taproot_psbt_to_dict():
    psbt = SpecterPSBT(PSBT, Descriptor.from_string(DESC), "regtest")
    obj = psbt.to_dict()
    assert obj["inputs"][0]["taproot_bip32_derivs"] == [
        {
            "pubkey": "eb3ac0b88386d1144bfba36795e8f8ec9974484cd732c03923a0a13721764470",
            "master_fingerprint": "73c5da0a",
            "path": "m/86h/1h/0h/0/0",
            "leaf_hashes": [],
        }
    ]
    assert (
        obj["inputs"][0]["taproot_internal_key"]
        == "eb3ac0b88386d1144bfba36795e8f8ec9974484cd732c03923a0a13721764470"
    )

    assert obj["outputs"][1]["taproot_bip32_derivs"] == [
        {
            "pubkey": "f17f4d482f79c9abece9a7d91683dff5ae116c5992fc8a0155fc16d45032775a",
            "master_fingerprint": "73c5da0a",
            "path": "m/86h/1h/0h/1/1",
            "leaf_hashes": [],
        }
    ]
    assert (
        obj["outputs"][1]["taproot_internal_key"]
        == "f17f4d482f79c9abece9a7d91683dff5ae116c5992fc8a0155fc16d45032775a"
    )
    assert obj["outputs"][1]["change"] == True
    assert obj["outputs"][1]["is_mine"] == True
    assert obj["inputs"][0]["is_mine"] == True
