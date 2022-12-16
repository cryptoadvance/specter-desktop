"""
Manages the list of addresses for the wallet, including labels and derivation paths
"""
import os
from .persistence import write_csv, read_csv
import logging

logger = logging.getLogger(__name__)


def to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    return v == "True"


class Address(dict):
    columns = [
        "address",  # str, address itself
        "index",  # int, derivation index
        "change",  # bool, change or receive
        "label",  # str, address label
        "used",  # bool, does this address have a transaction?
        "service_id",  # str, reserved for or used by Service.id
    ]
    type_converter = [
        str,
        int,
        to_bool,
        str,
        to_bool,
        str,
    ]

    def __init__(self, rpc, **kwargs):
        self.rpc = rpc
        # copy
        kwargs = dict(**kwargs)
        # replace with None or convert
        for i, k in enumerate(self.columns):
            v = kwargs.get(k, "")
            kwargs[k] = None if v in ["", None] else self.type_converter[i](v)

        super().__init__(**kwargs)

    def set_label(self, label):
        if self["label"] == label:
            return
        self["label"] = label
        self.rpc.setlabel(self.address, label)

    def set_service_id(self, service_id: str):
        if service_id:
            # Declares that this Address is associated with a Service
            self["service_id"] = service_id
        else:
            # Frees a reserved Address; reset its label
            self["service_id"] = None
            if not self.used and self["label"]:
                self.set_label("")

    @property
    def is_external(self):
        return self.index is None

    @property
    def is_mine(self):
        return not self.is_external

    @property
    def is_receiving(self):
        return self.is_mine and not self.change

    @property
    def is_change(self):
        return self.is_mine and self.change

    @property
    def index(self):
        return self["index"]

    @property
    def address(self):
        return self["address"]

    @property
    def change(self):
        return self["change"]

    @property
    def used(self):
        return self["used"]

    @property
    def label(self):
        if self["label"]:
            return self["label"]
        if self["change"] is not None and self["index"] is not None:
            prefix = "Change #" if self.change else "Address #"
            index = self["index"]
            return f"{prefix}{index}"
        return self.address

    @property
    def is_labeled(self):
        return bool(self["label"])

    @property
    def is_reserved(self):
        return bool(self["service_id"])

    @property
    def service_id(self):
        return self["service_id"]

    def __str__(self):
        return self.address

    def __repr__(self):
        if self.label != self.address:
            return f"Address({self.label}, {self.address})"
        else:
            return f"Address({self.address})"


class AddressList(dict):
    AddressCls = Address

    def __init__(self, path, rpc):
        super().__init__()
        self.path = path
        self.rpc = rpc
        file_exists = False
        if os.path.isfile(self.path):
            try:
                addresses = read_csv(self.path, self.AddressCls, self.rpc)
                # dict allows faster lookups
                for addr in addresses:
                    self[addr.address] = addr
                file_exists = True
            except Exception as e:
                logger.exception(e)
        self._file_exists = file_exists

    def save(self):
        if len(list(self.keys())) > 0:
            write_csv(self.path, list(self.values()), self.AddressCls)
        self._file_exists = True

    def set_labels(self, arr):
        """
        Sets the labels for existing addresses

        arr should be a list with dicts, example:
            [{'address':'bc1qabc...', 'label':'mylabel1'}, {'address':'bc1qabd...', 'label':'mylabel2'}, ...]
        """
        for addr in arr:
            if addr["address"] in self:
                self[addr["address"]].set_label(addr["label"])
        self.save()

    def add(self, arr, check_rpc=False):
        """
        arr should be a list with dicts, example:
            [{'address':'bc1qabc...', 'label':'mylabel1'}, {'address':'bc1qabd...', 'label':'mylabel2'}, ...]
        """
        labeled_addresses = {}
        if check_rpc:
            # get all available labels
            labels = self.rpc.listlabels()
            if "" in labels:
                labels.remove("")
            # get addresses for all labels
            res = self.rpc.multi([("getaddressesbylabel", label) for label in labels])
            for i, result in enumerate(res):
                label = labels[i]
                # go through all addresses and assign labels
                for k in result["result"].keys():
                    labeled_addresses[k] = label
        # go through all addresses and assign
        for addr in arr:
            if addr["address"] in self:
                continue
            # if we found a label for it - import
            if addr["address"] in labeled_addresses:
                addr["label"] = labeled_addresses[addr["address"]]
            self[addr["address"]] = self.AddressCls(self.rpc, **addr)
        # add all labeled addresses but not from the array (destination)
        for addr in labeled_addresses:
            if addr not in self:
                self[addr] = self.AddressCls(
                    self.rpc,
                    address=addr,
                    label=labeled_addresses[addr],
                    change=None,
                    index=None,
                )
        self.save()

    def get_address(self, address: str) -> Address:
        if address not in self:
            self[address] = self.AddressCls(self.rpc, address=address)
        return self[address]

    def set_label(self, address, label):
        addr_obj = self.get_address(address)
        addr_obj.set_label(label)
        self.save()

    def get_labels(self):
        labels = {}
        for addr in self.values():
            lbl = addr.get("label", "")
            if lbl:
                labels[lbl] = labels.get(lbl, []) + [addr.address]
        return labels

    def associate_with_service(
        self, address: str, service_id: str, label: str, autosave: bool = True
    ):
        """
        Associates the Address (i.e. sets Address.service_id) with the specified
        Service.id.
        """
        addr_obj = self.get_address(address)
        addr_obj.set_service_id(service_id)
        addr_obj.set_label(label)
        if autosave:
            self.save()

    def deassociate(self, address: str, autosave: bool = True):
        """
        Removes the Address's association with a Service (i.e. sets
        Address.service_id to None and resets Address.label).
        """
        addr_obj = self.get_address(address)
        addr_obj.set_service_id(None)
        if autosave:
            self.save()

    def set_used(self, addresses):
        need_save = False
        for address in addresses:
            if address not in self:
                # external maybe???
                continue
            addr = self[address]
            # doesn't make sense to set used for external addresses
            if addr.is_external or addr.used:
                continue
            addr["used"] = True
            need_save = True
        if need_save:
            self.save()

    def max_index(self, change=False):
        return max(
            0,
            0,
            *[
                addr.index or 0
                for addr in self.values()
                if addr.is_mine and addr.change == change
            ],
        )

    def max_used_index(self, change=False):
        return max(
            -1,
            -1,
            *[
                addr.index or -1
                for addr in self.values()
                if addr.is_mine and addr.used and addr.change == change
            ],
        )

    @property
    def file_exists(self):
        return self._file_exists and os.path.isfile(self.path)
