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
        self.search_function = search_function
        self.title = title
        self.endpoint = endpoint

    def nodes_with_search_function(self):
        "Typically the nodes having a search_function, are childless nodes."
        nodes = []
        if self.search_function:
            nodes += [self]

        for child in self.children:
            nodes += child.nodes_with_search_function()
        return nodes

    def flattened_parent_list(self):
        parents = []
        if self.parent:
            parents = self.parent.flattened_parent_list() + [self.parent]

        return parents

    def json(self):
        d = {}
        d["ids"] = self.ids
        d["flattened_parent_list"] = [
            parent.json() for parent in self.flattened_parent_list()
        ]
        d["title"] = self.title
        d["endpoint"] = self.endpoint
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

    def _search_in_structure(
        self, search_term, structure, title_key=None, title=None, key=None
    ):
        """
        Recursively goes through the dict/list/tuple/set structure and matches (case insensitive) the search_term

        Args:
            search_term (str): _description_
            structure (list, tuple, set, dict): _description_
            title_key (_type_, optional): If a result is found in a dictionary, then the value of the title_key
                                            is used as the title of the SearchResult, e.g,
                                            the title_key="txid" is the title of a search result in a tx-dictionary.
                                            Defaults to None.

        Returns:
            results: list of SearchResult
        """
        results = []
        if isinstance(structure, dict):
            for key, value in structure.items():
                results += self._search_in_structure(
                    search_term,
                    value,
                    title_key=title_key,
                    title=structure.get(title_key),
                    key=key,
                )
        elif isinstance(structure, (list, tuple, set)):
            for value in structure:
                results += self._search_in_structure(
                    search_term, value, title_key=title_key, title=title, key=key
                )
        elif search_term.lower() in str(structure).lower():
            results += [SearchResult(structure, title=title, key=key)]

        return results

    def _search_in_ui_structure(self, search_term, html_root):
        """
        Applies search_function(search_term) to all nodes, which have a search_function

        Args:
            search_term (_type_): _description_
            html_root (_type_): _description_

        Returns:
            list of dict: Example:
                [{
                    'ui_element': {
                        'ids': ('tx-table-tr', 'shadowRoot', 'btn_history'),
                        'flattened_parent_list': [{
                            'ids': set(),
                            'flattened_parent_list': [],
                            'title': None,
                            'endpoint': None
                        }],
                        'title': 'History',
                        'endpoint': '/wallets/wallet/tr/history/txlist/'
                    },
                    'search_hits': [{
                        'title': '599a2780545f456b69feac58a1e4ef8271a81a367c08315cffd3e91e2e23f95a',
                        'key': 'Blockhash',
                        'value': '65dc072035e1f870963a111a188e14a7359454b02a09210ead68250a051f6b16'
                    }]
                }]
        """
        result_dicts = []
        for node in html_root.nodes_with_search_function():
            result_dict = {
                "ui_element": node.json(),
                "search_hits": [
                    hit.json() for hit in node.search_function(search_term)
                ],
            }
            if result_dict["search_hits"]:
                result_dicts.append(result_dict)
        return result_dicts

    def do_global_search(
        self,
        search_term,
        user_id,
        wallet_manager,
        device_manager,
        force_build_ui_tree=False,
    ):
        "Builds the UI Tree if necessary (only do it once) and then calls the functions in it to search for the search_term"
        if (user_id not in self.ui_roots) or force_build_ui_tree:
            logger.debug(f"Building UI Tree for user {user_id}")
            self.ui_roots[user_id] = self._build_ui_elements(
                wallet_manager, device_manager
            )

        result_dicts = (
            self._search_in_ui_structure(search_term, self.ui_roots[user_id])
            if len(search_term) > 1
            else []
        )

        return {
            "result_dicts": result_dicts,
            "search_term": search_term,
        }
