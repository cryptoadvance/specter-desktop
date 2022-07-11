import os
import logging

from flask import url_for

logger = logging.getLogger(__name__)


class HtmlElement:
    "This is a way to reconstruct the HTML Logical UI Tree and sum up results nicely"

    def __init__(
        self,
        parent,
        id=None,
        function=None,
        children=None,
        visible_on_endpoints="/",
        filter_via_input_ids=None,
    ):
        self.parent = parent
        if self.parent:
            self.parent.children.add(self)
        self.children = children if children else set()
        self.id = id if id else set()
        self._result = None
        self.function = function
        self.visible_on_endpoints = visible_on_endpoints
        self.filter_via_input_ids = filter_via_input_ids

    @property
    def result(self):
        if self._result:
            return self._result
        else:
            return sum([child.result for child in self.children])

    @result.setter
    def result(self, result):
        if self.children:
            raise "Setting results is only allowed for end nodes"
        self._result = result

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
            node.result = None

    def flattened_sub_tree_as_json(self):
        result_list = [self.json()]
        for child in self.children:
            result_list += child.flattened_sub_tree_as_json()
        return result_list

    def json(self):
        d = {}
        d["id"] = self.id
        d["children"] = self.children
        d["result"] = self.result
        d["visible_on_endpoints"] = self.visible_on_endpoints
        d["filter_via_input_ids"] = self.filter_via_input_ids
        return d


HTML_ROOT = None


def build_html_elements(specter):
    """
    This builds all HtmlElements that should be highlighted during a search.
    It also encodes which functions will be used for searching.

    Returns:
        HtmlElement: This is the html_root, which has all children linked inside
    """
    html_root = HtmlElement(None)
    wallets = HtmlElement(html_root, id="toggle_wallets_list")
    devices = HtmlElement(html_root, id="toggle_devices_list")

    def search_in_structure(search_term, l):
        count = 0
        for item in l:
            if isinstance(item, dict):
                count += search_in_structure(search_term, item.values())
            elif isinstance(item, list):
                count += search_in_structure(search_term, item)
            elif search_term.lower() in str(item).lower():
                count += 1
        return count

    def add_all_in_wallet(wallet):
        sidebar_wallet = HtmlElement(wallets, id=f"{wallet.alias}-sidebar-list-item")
        wallet_names = HtmlElement(
            sidebar_wallet,
            id="title",
            function=lambda x: search_in_structure(x, [wallet.alias]),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )
        transactions = HtmlElement(
            sidebar_wallet,
            id="btn_transactions",
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
            filter_via_input_ids=(
                f"tx-table-{wallet.alias}",
                "shadowRoot",
                "search_input",
            ),
        )
        transactions_history = HtmlElement(
            transactions,
            id=(
                f"tx-table-{wallet.alias}",
                "shadowRoot",
                "btn_history",
            ),
            function=lambda x: search_in_structure(x, wallet.txlist()),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )
        transactions_utxo = HtmlElement(
            transactions,
            id=(
                f"tx-table-{wallet.alias}",
                "shadowRoot",
                "btn_utxo",
            ),
            function=lambda x: search_in_structure(x, wallet.full_utxo),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )

        addresses = HtmlElement(
            sidebar_wallet,
            id="btn_addresses",
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )
        addresses_recieve = HtmlElement(
            addresses,
            id=(
                f"addresses-table-{wallet.alias}",
                "shadowRoot",
                "receive-addresses-view-btn",
            ),
            function=lambda x: search_in_structure(
                x, wallet.addresses_info(is_change=False)
            ),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )
        addresses_change = HtmlElement(
            addresses,
            id=(
                f"addresses-table-{wallet.alias}",
                "shadowRoot",
                "change-addresses-view-btn",
            ),
            function=lambda x: search_in_structure(
                x, wallet.addresses_info(is_change=True)
            ),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )

        recieve = HtmlElement(
            sidebar_wallet,
            id="btn_receive",
            function=lambda x: search_in_structure(x, [wallet.address]),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )

        send = HtmlElement(
            sidebar_wallet,
            id="btn_send",
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )
        unsigned = HtmlElement(
            send,
            id="btn_send_pending",
            function=lambda x: search_in_structure(
                x, [psbt.to_dict() for psbt in wallet.pending_psbts.values()]
            ),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )

    def add_all_in_devices(device):
        sidebar_device = HtmlElement(devices, id=f"device_list_item_{device.alias}")
        device_names = HtmlElement(
            sidebar_device,
            id="title",
            function=lambda x: search_in_structure(x, [device.alias]),
        )
        device_keys = HtmlElement(
            sidebar_device,
            id="keys-table-header-key",
            function=lambda x: search_in_structure(x, [key for key in device.keys]),
            visible_on_endpoints=[
                url_for("devices_endpoint.device", device_alias=device.alias)
            ],
        )

    for wallet in specter.wallet_manager.wallets.values():
        add_all_in_wallet(wallet)
    for device in specter.device_manager.devices.values():
        add_all_in_devices(device)
    return html_root


def apply_search_on_dict(search_term, html_root):
    "Given an html_root it will call the child.function for all childs that do not have any children"
    end_nodes = html_root.calculate_end_nodes()
    for end_node in end_nodes:
        end_node.result = end_node.function(search_term)
    return html_root


def do_global_search(search_term, specter):
    "Builds the HTML Tree if ncessary (only do it once) and then calls the functions in it to search for the search_term"
    global HTML_ROOT
    if not HTML_ROOT:
        HTML_ROOT = build_html_elements(specter)
    else:
        HTML_ROOT.reset_results()
    print(HTML_ROOT)

    if search_term:
        apply_search_on_dict(search_term, HTML_ROOT)
    print(HTML_ROOT.flattened_sub_tree_as_json())
    return {
        "tree": HTML_ROOT,
        "list": HTML_ROOT.flattened_sub_tree_as_json(),
        "search_term": search_term,
    }
