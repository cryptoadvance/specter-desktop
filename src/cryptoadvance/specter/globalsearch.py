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
        result_list = [self.to_json()]
        for child in self.children:
            result_list += child.flattened_sub_tree_as_json()
        return result_list

    def to_json(self):
        d = {}
        d["id"] = self.id
        d["children"] = self.children
        d["result"] = self.result
        d["visible_on_endpoints"] = self.visible_on_endpoints
        d["filter_via_input_ids"] = self.filter_via_input_ids
        return d


HTML_ROOT = None


def build_html_elements(specter):
    html_root = HtmlElement(None)
    wallets = HtmlElement(html_root, id="toggle_wallets_list")

    def search_in_structure(search_term, l):
        count = 0
        for item in l:
            if isinstance(item, dict):
                count += search_in_structure(search_term, item.values())
            elif isinstance(item, list):
                count += search_in_structure(search_term, item)
            elif search_term in str(item):
                count += 1
        return count

    def add_all_in_wallet(wallet):
        sidebar_wallet = HtmlElement(wallets, id=f"{wallet.alias}-sidebar-list-item")
        transactions = HtmlElement(
            sidebar_wallet,
            id="btn_transactions",
            function=lambda x: search_in_structure(
                x, [tx.__dict__() for tx in wallet.transactions.values()]
            ),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
            filter_via_input_ids=(
                f"tx-table-{wallet.alias}",
                "shadowRoot",
                "search_input",
            ),
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
            id="receive-addresses-view-btn",
            function=lambda x: search_in_structure(x, wallet.addresses),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )
        addresses_change = HtmlElement(
            addresses,
            id="change-addresses-view-btn",
            function=lambda x: search_in_structure(x, wallet.change_addresses),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )

        current_recieve_address = HtmlElement(
            sidebar_wallet,
            id="btn_receive",
            function=lambda x: search_in_structure(x, [wallet.address]),
            visible_on_endpoints=[
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ],
        )

    for wallet in specter.wallet_manager.wallets.values():
        add_all_in_wallet(wallet)
    return html_root


def apply_search_on_dict(search_term, html_root):
    end_nodes = html_root.calculate_end_nodes()
    for end_node in end_nodes:
        end_node.result = end_node.function(search_term)
    return html_root


def do_global_search(search_term, specter):
    global HTML_ROOT
    if not HTML_ROOT:
        HTML_ROOT = build_html_elements(specter)
    else:
        HTML_ROOT.reset_results()
    print(HTML_ROOT)

    if search_term:
        apply_search_on_dict(search_term, HTML_ROOT)
    print(HTML_ROOT.flattened_sub_tree_as_json())
    return {"tree": HTML_ROOT, "list": HTML_ROOT.flattened_sub_tree_as_json()}
