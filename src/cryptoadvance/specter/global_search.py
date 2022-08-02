import os
import logging

from flask import url_for

logger = logging.getLogger(__name__)


class UIElement:
    """
    This is a logical struture representing an UI/enpoint/HTML element, e.g., a button, a tab.

    Multiple of these elements can be attached to each other, by referencing the parent element during __init__

    This is not a full reconstruction of the HTML DOM tree, but only the most necessary part to represent the logical structure
    the user sees. And only these parts which are included in the search.
    """

    def __init__(
        self,
        parent,
        ids=None,
        function=None,
        children=None,
        title=None,
        endpoint=None,
    ):
        self.parent = parent
        if self.parent:
            self.parent.children.add(self)
        self.children = children if children else set()
        # the ids is the html id or, if needed the set of concatenated ids to get to the html element
        self.ids = ids if ids else set()
        self._results = None
        self.function = function
        self.title = title
        self.endpoint = endpoint

    @property
    def results(self):
        if self._results:
            return self._results
        else:
            flattended_list = []
            for child in self.children:
                flattended_list += child.results
            return flattended_list

    @results.setter
    def results(self, results):
        if self.children:
            raise "Setting results is only allowed for end nodes"
        self._results = results

    def calculate_end_nodes(self):
        if not self.children:
            return [self]

        end_nodes = []
        for child in self.children:
            end_nodes += child.calculate_end_nodes()
        return end_nodes

    def reset_results(self):
        end_nodes = self.calculate_end_nodes()
        for node in end_nodes:
            node.results = []

    def flattened_sub_tree_as_json(self):
        result_list = [self.json()]
        for child in self.children:
            result_list += child.flattened_sub_tree_as_json()
        return result_list

    def flattened_parent_list(self):
        parents = []
        if self.parent:
            parents = self.parent.flattened_parent_list() + [self.parent]

        return parents

    def childless_only_as_json(self):
        result_list = []

        if not self.children:
            return [self.json(include_results=True)] if self.results else []

        for child in self.children:
            result_list += child.childless_only_as_json()

        return result_list

    def json(self, include_results=False):
        d = {}
        d["ids"] = self.ids
        d["flattened_parent_list"] = [
            parent.json() for parent in self.flattened_parent_list()
        ]
        d["title"] = self.title
        d["endpoint"] = self.endpoint
        if include_results:
            d["results"] = self.results
        return d


HTML_ROOT = None


def search_in_structure(search_term, structure):
    results = []
    for item in structure:
        if isinstance(item, dict):
            results += search_in_structure(search_term, item.values())
        elif isinstance(item, list):
            results += search_in_structure(search_term, item)
        elif search_term.lower() in str(item).lower():
            results += [str(item)]
    return results


def add_all_in_wallet(html_wallets, wallet):
    sidebar_wallet = UIElement(
        html_wallets,
        ids=f"{wallet.alias}-sidebar-list-item",
        title=wallet.alias,
    )
    wallet_names = UIElement(
        sidebar_wallet,
        ids="title",
        title="Wallet",
        endpoint=url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias),
        function=lambda x: search_in_structure(x, [wallet.alias]),
    )
    transactions = UIElement(
        sidebar_wallet,
        ids="btn_transactions",
        title="Transactions",
        endpoint=url_for("wallets_endpoint.history", wallet_alias=wallet.alias),
    )
    transactions_history = UIElement(
        transactions,
        ids=(
            f"tx-table-{wallet.alias}",
            "shadowRoot",
            "btn_history",
        ),
        title="History",
        endpoint=url_for(
            "wallets_endpoint.history_tx_list_type",
            wallet_alias=wallet.alias,
            tx_list_type="txlist",
        ),
        function=lambda x: search_in_structure(x, wallet.txlist()),
    )
    transactions_utxo = UIElement(
        transactions,
        ids=(
            f"tx-table-{wallet.alias}",
            "shadowRoot",
            "btn_utxo",
        ),
        title="UTXO",
        endpoint=url_for(
            "wallets_endpoint.history_tx_list_type",
            wallet_alias=wallet.alias,
            tx_list_type="utxo",
        ),
        function=lambda x: search_in_structure(x, wallet.full_utxo),
    )

    addresses = UIElement(
        sidebar_wallet,
        ids="btn_addresses",
        title="Addresses",
        endpoint=url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias),
    )
    addresses_recieve = UIElement(
        addresses,
        ids=(
            f"addresses-table-{wallet.alias}",
            "shadowRoot",
            "receive-addresses-view-btn",
        ),
        title="Recieve Addresses",
        endpoint=url_for(
            "wallets_endpoint.addresses_with_type",
            wallet_alias=wallet.alias,
            address_type="recieve",
        ),
        function=lambda x: search_in_structure(
            x, wallet.addresses_info(is_change=False)
        ),
    )
    addresses_change = UIElement(
        addresses,
        ids=(
            f"addresses-table-{wallet.alias}",
            "shadowRoot",
            "change-addresses-view-btn",
        ),
        title="Change Addresses",
        endpoint=url_for(
            "wallets_endpoint.addresses_with_type",
            wallet_alias=wallet.alias,
            address_type="change",
        ),
        function=lambda x: search_in_structure(
            x, wallet.addresses_info(is_change=True)
        ),
    )

    recieve = UIElement(
        sidebar_wallet,
        ids="btn_receive",
        title="Recieve",
        endpoint=url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias),
        function=lambda x: search_in_structure(x, [wallet.address]),
    )

    send = UIElement(
        sidebar_wallet,
        ids="btn_send",
        title="Send",
        endpoint=url_for("wallets_endpoint.send_new", wallet_alias=wallet.alias),
    )
    unsigned = UIElement(
        send,
        ids="btn_send_pending",
        title="Unsigned",
        endpoint=url_for("wallets_endpoint.send_pending", wallet_alias=wallet.alias),
        function=lambda x: search_in_structure(
            x, [psbt.to_dict() for psbt in wallet.pending_psbts.values()]
        ),
    )


def add_all_in_devices(html_devices, device):
    sidebar_device = UIElement(
        html_devices,
        ids=f"device_list_item_{device.alias}",
        title=device.alias,
        endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
    )
    device_names = UIElement(
        sidebar_device,
        ids="title",
        title="Devices",
        endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
        function=lambda x: search_in_structure(x, [device.alias]),
    )
    device_keys = UIElement(
        sidebar_device,
        ids="keys-table-header-key",
        title="Keys",
        endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
        function=lambda x: search_in_structure(x, [key for key in device.keys]),
    )


def build_html_elements(specter):
    """
    This builds all UIElements that should be highlighted during a search.
    It also encodes which functions will be used for searching.

    Returns:
        UIElement: This is the html_root, which has all children linked in a tree
    """
    html_root = UIElement(None)
    html_wallets = UIElement(
        html_root,
        ids="toggle_wallets_list",
        title="Wallets",
        endpoint=url_for("wallets_endpoint.wallets_overview"),
    )
    html_devices = UIElement(
        html_root,
        ids="toggle_devices_list",
        title="Devices",
        endpoint=url_for("wallets_endpoint.wallets_overview"),
    )

    for wallet in specter.wallet_manager.wallets.values():
        add_all_in_wallet(html_wallets, wallet)
    for device in specter.device_manager.devices.values():
        add_all_in_devices(html_devices, device)
    return html_root


def search_in_html_structure(search_term, html_root):
    "Given an html_root it will call the child.function for all childs that do not have any children"
    end_nodes = html_root.calculate_end_nodes()
    for end_node in end_nodes:
        end_node.results = end_node.function(search_term)
    return html_root


def do_global_search(search_term, specter):
    "Builds the HTML Tree if ncessary (only do it once) and then calls the functions in it to search for the search_term"
    global HTML_ROOT
    if not HTML_ROOT:
        HTML_ROOT = build_html_elements(specter)
    else:
        HTML_ROOT.reset_results()

    if search_term:
        search_in_html_structure(search_term, HTML_ROOT)

    # print(HTML_ROOT.childless_only_as_json())

    return {
        "childless_only": HTML_ROOT.childless_only_as_json(),
        "search_term": search_term,
    }
