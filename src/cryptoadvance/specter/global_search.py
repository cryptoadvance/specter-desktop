import os
import logging

from flask import url_for

logger = logging.getLogger(__name__)


class SearchResult:
    def __init__(self, value, title=None, key=None) -> None:
        self.title = str(title) if title else title
        self.key = str(key).capitalize() if key else key
        self.value = str(value) if value else value

    def json(self):
        return self.__dict__


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
        search_function=None,
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
        self.search_function = search_function
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
        """
        Set a result list for end-nodes (childless nodes)

        Args:
            results (list of SearchResult): _description_
        """
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
            d["results"] = [result.json() for result in self.results]
        return d


class GlobalSearchTrees:
    "holds the diffferent UI roots of different users"

    def __init__(self):
        self.ui_roots = {}

    def _wallet_ui_elements(self, ui_root, wallet):
        html_wallets = UIElement(
            ui_root,
            ids="toggle_wallets_list",
            title="Wallets",
            endpoint=url_for("wallets_endpoint.wallets_overview"),
        )

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
            search_function=lambda x: self._search_in_structure(x, [wallet.alias]),
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
            search_function=lambda x: self._search_in_structure(
                x, wallet.txlist(), title_key="txid"
            ),
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
            search_function=lambda x: self._search_in_structure(
                x, wallet.full_utxo, title_key="txid"
            ),
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
            search_function=lambda x: self._search_in_structure(
                x, wallet.addresses_info(is_change=False), title_key="address"
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
            search_function=lambda x: self._search_in_structure(
                x, wallet.addresses_info(is_change=True), title_key="address"
            ),
        )

        recieve = UIElement(
            sidebar_wallet,
            ids="btn_receive",
            title="Recieve",
            endpoint=url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias),
            search_function=lambda x: self._search_in_structure(
                x, [wallet.address], title_key="address"
            ),
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
            endpoint=url_for(
                "wallets_endpoint.send_pending", wallet_alias=wallet.alias
            ),
            search_function=lambda x: self._search_in_structure(
                x,
                [psbt.to_dict() for psbt in wallet.pending_psbts.values()],
                title_key="address",
            ),
        )

    def _device_ui_elements(self, ui_root, device):
        html_devices = UIElement(
            ui_root,
            ids="toggle_devices_list",
            title="Devices",
            endpoint=url_for("wallets_endpoint.wallets_overview"),
        )

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
            search_function=lambda x: self._search_in_structure(x, [device.alias]),
        )
        device_keys = UIElement(
            sidebar_device,
            ids="keys-table-header-key",
            title="Keys",
            endpoint=url_for("devices_endpoint.device", device_alias=device.alias),
            search_function=lambda x: self._search_in_structure(
                x, [key for key in device.keys], title_key="purpose"
            ),
        )

    def _build_ui_elements(self, wallet_manager, device_manager):
        """
        This builds all UIElements that should be highlighted during a search.
        It also encodes which functions will be used for searching.

        Returns:
            UIElement: This is the html_root, which has all children linked in a tree
        """
        ui_root = UIElement(None)
        for wallet in wallet_manager.wallets.values():
            self._wallet_ui_elements(ui_root, wallet)
        for device in device_manager.devices.values():
            self._device_ui_elements(ui_root, device)
        return ui_root

    def _search_in_dict(self, search_term, d, title_key=None):
        results = []
        for key, value in d.items():
            if isinstance(value, dict):
                results += self._search_in_dict(search_term, value, title_key=title_key)
            elif isinstance(value, (list, set)):
                results += self._search_in_structure(
                    search_term, value, title_key=title_key
                )
            elif search_term.lower() in str(value).lower():
                results += [SearchResult(value, title=d.get(title_key), key=key)]
        return results

    def _search_in_structure(self, search_term, structure, title_key=None):
        results = []
        if isinstance(structure, dict):
            return self._search_in_dict(search_term, structure)

        for i, value in enumerate(structure):
            if isinstance(value, dict):
                results += self._search_in_dict(search_term, value, title_key=title_key)
            elif isinstance(value, (list, set)):
                results += self._search_in_structure(
                    search_term, value, title_key=title_key
                )
            elif search_term.lower() in str(value).lower():
                results += [SearchResult(value)]
        return results

    def _search_in_ui_structure(self, search_term, html_root):
        "Given an html_root it will call the child.search_function for all childs that do not have any children"
        end_nodes = html_root.calculate_end_nodes()
        for end_node in end_nodes:
            end_node.results = end_node.search_function(search_term)
        return html_root

    def do_global_search(self, search_term, user_id, wallet_manager, device_manager):
        "Builds the UI Tree if ncessary (only do it once) and then calls the functions in it to search for the search_term"
        if user_id not in self.ui_roots:
            logger.debug(f"Building UI Tree for user {user_id}")
            self.ui_roots[user_id] = self._build_ui_elements(
                wallet_manager, device_manager
            )
        else:
            self.ui_roots[user_id].reset_results()

        if len(search_term) > 1:
            self._search_in_ui_structure(search_term, self.ui_roots[user_id])

        return {
            "childless_only": self.ui_roots[user_id].childless_only_as_json(),
            "search_term": search_term,
        }
