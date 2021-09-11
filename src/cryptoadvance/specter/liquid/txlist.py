from ..txlist import *
from embit.liquid.transaction import LTransaction


class LTxItem(TxItem):
    TransactionCls = LTransaction
    columns = [
        "txid",  # str, txid in hex
        "blockhash",  # str, blockhash, None if not confirmed
        "blockheight",  # int, blockheight, None if not confirmed
        "time",  # int (timestamp in seconds), time received
        "bip125-replaceable",  # str ("yes" / "no"), whatever RBF is enabled for the transaction
        "conflicts",  # rbf conflicts, list of txids
        "vsize",
        "category",
        "address",
        "amount",
        "asset",
        "ismine",
    ]
    type_converter = [
        str,
        str,
        int,
        int,
        str,
        parse_arr,
        int,
        str,
        parse_arr,
        parse_arr,
        parse_arr,
        bool,
    ]

    def __dict__(self):
        return {
            "txid": self["txid"],
            "blockhash": self["blockhash"],
            "blockheight": self["blockheight"],
            "time": self["time"],
            "conflicts": self["conflicts"],
            "bip125-replaceable": self["bip125-replaceable"],
            "vsize": self["vsize"],
            "category": self["category"],
            "address": self["address"],
            "amount": self["amount"],
            "asset": self["asset"],
            "ismine": self["ismine"],
        }


class LTxList(TxList):
    ItemCls = LTxItem
    counter = 0

    def fill_missing(self, tx):
        raw_tx = self.decoderawtransaction(tx.hex)
        tx["vsize"] = raw_tx["vsize"]

        category = ""
        addresses = []
        amounts = {}
        assets = {}
        inputs_mine_count = 0
        for vin in raw_tx["vin"]:
            # coinbase tx
            if (
                vin["txid"]
                == "0000000000000000000000000000000000000000000000000000000000000000"
            ):
                category = "generate"
                break
            if vin["txid"] in self:
                try:
                    address = get_address_from_dict(
                        self.decoderawtransaction(self[vin["txid"]].hex)["vout"][
                            vin["vout"]
                        ]
                    )
                    address_info = self._addresses.get(address, None)
                    if address_info and not address_info.is_external:
                        inputs_mine_count += 1
                except Exception as e:
                    logger.error(e)
                    continue

        outputs_mine_count = 0
        for out in raw_tx["vout"]:
            try:
                address = get_address_from_dict(out)
            except Exception as e:
                # couldn't get address...
                logger.error(e)
                continue
            address_info = self._addresses.get(address)
            if address_info and not address_info.is_external:
                outputs_mine_count += 1
            addresses.append(address)
            amounts[address] = out.get("value", 0)
            assets[address] = out.get("asset", "Unknown")

        if inputs_mine_count:
            if outputs_mine_count == len(raw_tx["vout"]):
                category = "selftransfer"
                # remove change addresses from the dest list
                addresses2 = [
                    address
                    for address in addresses
                    if self._addresses.get(address, None)
                    and not self._addresses[address].change
                ]
                # use new list only if it's not empty
                if addresses2:
                    addresses = addresses2
            else:
                category = "send"
                addresses = [
                    address
                    for address in addresses
                    if not self._addresses.get(address, None)
                    or self._addresses[address].is_external
                ]
        else:
            if not category:
                category = "receive"
            addresses = [
                address
                for address in addresses
                if self._addresses.get(address, None)
                and not self._addresses[address].is_external
            ]

        amounts = [amounts[address] for address in addresses]
        assets = [assets[address] for address in addresses]

        if len(addresses) == 1:
            addresses = addresses[0]
            amounts = amounts[0]
            assets = assets[0]

        tx["category"] = category
        tx["address"] = addresses
        tx["amount"] = amounts
        tx["asset"] = assets
        if not addresses:
            tx["ismine"] = False
        else:
            tx["ismine"] = True

    def decoderawtransaction(self, txhex):
        # TODO: using rpc for now, can be moved to utils
        return self.rpc.decoderawtransaction(txhex)
