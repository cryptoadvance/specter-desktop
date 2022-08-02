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
        title=None,
        endpoint=None,
        click_on_id=False,  # some tabs do not have their own endpoint but need a click to show the tab
        filter_via_input_ids=None,
    ):
        self.parent = parent
        if self.parent:
            self.parent.children.add(self)
        self.children = children if children else set()
        # the id is the html id or, if needed the set of concatenated ids to get to the html element
        self.id = id if id else set()
        self._result = None
        self.function = function
        self.filter_via_input_ids = filter_via_input_ids
        self.title = title
        self.endpoint = endpoint
        self.click_on_id = click_on_id

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

    def childless_only_as_json(self, only_with_result=True):
        result_list = []
        if only_with_result and not self.result:
            return result_list

        for child in self.children:
            result_list += child.childless_only_as_json()

        if not self.children:
            result_list += [self.json()]
        return result_list

    def flattened_parent_list(self):
        parents = []
        if self.parent:
            parents = self.parent.flattened_parent_list() + [self.parent]

        return parents

    def json(self):
        d = {}
        d["id"] = self.id
        # d["children"] = {child.json() for child in self.children}
        d["parents"] = self.parent.json() if self.parent else self.parent
        d["flattened_parent_list"] = [
            parent.json() for parent in self.flattened_parent_list()
        ]
        d["result"] = self.result
        d["title"] = self.title
        d["endpoint"] = self.endpoint
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
    wallets = HtmlElement(
        html_root,
        id="toggle_wallets_list",
        title="Wallets",
        endpoint=url_for("wallets_endpoint.wallets_overview"),
    )
    devices = HtmlElement(
        html_root,
        id="toggle_devices_list",
        title="Devices",
        endpoint=url_for("wallets_endpoint.wallets_overview"),
    )

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
        sidebar_wallet = HtmlElement(
            wallets,
            id=f"{wallet.alias}-sidebar-list-item",
            title=wallet.alias,
        )
        wallet_names = HtmlElement(
            sidebar_wallet,
            id="title",
            title="Wallet",
            endpoint=url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias),
            function=lambda x: search_in_structure(x, [wallet.alias]),
        )
        transactions = HtmlElement(
            sidebar_wallet,
            id="btn_transactions",
            title="Transactions",
            endpoint=url_for("wallets_endpoint.history", wallet_alias=wallet.alias),
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
            title="History",
            endpoint=url_for(
                "wallets_endpoint.history_tx_list_type",
                wallet_alias=wallet.alias,
                tx_list_type="txlist",
            ),
            function=lambda x: search_in_structure(x, wallet.txlist()),
        )
        transactions_utxo = HtmlElement(
            transactions,
            id=(
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

        addresses = HtmlElement(
            sidebar_wallet,
            id="btn_addresses",
            title="Addresses",
            endpoint=url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias),
        )
        addresses_recieve = HtmlElement(
            addresses,
            id=(
                f"addresses-table-{wallet.alias}",
                "shadowRoot",
                "receive-addresses-view-btn",
            ),
            title="Recieve Addresses",
            endpoint=url_for("wallets_endpoint.receive", wallet_alias=wallet.alias),
            function=lambda x: search_in_structure(
                x, wallet.addresses_info(is_change=False)
            ),
        )
        addresses_change = HtmlElement(
            addresses,
            id=(
                f"addresses-table-{wallet.alias}",
                "shadowRoot",
                "change-addresses-view-btn",
            ),
            title="Change Addresses",
            endpoint=url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias),
            click_on_id=True,
            function=lambda x: search_in_structure(
                x, wallet.addresses_info(is_change=True)
            ),
        )

        recieve = HtmlElement(
            sidebar_wallet,
            id="btn_receive",
            title="Recieve",
            endpoint=url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias),
            function=lambda x: search_in_structure(x, [wallet.address]),
        )

        send = HtmlElement(
            sidebar_wallet,
            id="btn_send",
            title="Send",
            endpoint=url_for("wallets_endpoint.send_new", wallet_alias=wallet.alias),
        )
        unsigned = HtmlElement(
            send,
            id="btn_send_pending",
            title="Unsigned",
            endpoint=url_for(
                "wallets_endpoint.send_pending", wallet_alias=wallet.alias
            ),
            function=lambda x: search_in_structure(
                x, [psbt.to_dict() for psbt in wallet.pending_psbts.values()]
            ),
        )

    def add_all_in_devices(device):
        sidebar_device = HtmlElement(
            devices,
            id=f"device_list_item_{device.alias}",
            title=device.alias,
            endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
        )
        device_names = HtmlElement(
            sidebar_device,
            id="title",
            title="Devices",
            endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
            function=lambda x: search_in_structure(x, [device.alias]),
        )
        device_keys = HtmlElement(
            sidebar_device,
            id="keys-table-header-key",
            title="Keys",
            endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
            function=lambda x: search_in_structure(x, [key for key in device.keys]),
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
        "childless_only": HTML_ROOT.childless_only_as_json(),
        "list": HTML_ROOT.flattened_sub_tree_as_json(),
        "search_term": search_term,
    }
