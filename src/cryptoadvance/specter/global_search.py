import os
import logging, json
import types
from flask import url_for

logger = logging.getLogger(__name__)


class Endpoint:
    def __init__(self, url, method_str="href", form_data=None):
        """
        In the simple case this is just an url for href.
        It can also be a GET or POST request

        Args:
            url (str): _description_
            method_str (str, optional): "href", "form". Defaults to "href".
                "href" will make the url open as a simple link
                "form" will create a form together with the formData and url and submit it.
            form_data (dict, optional): _description_. Defaults to None.
        """
        self.url = url
        self.method_str = method_str
        self.form_data = form_data

    def json(self):
        return self.__dict__


class SearchResult:
    def __init__(self, value, title=None, key=None, endpoint=None) -> None:
        self.title = str(title) if title else title
        self.key = str(key).capitalize() if key else key
        self.value = str(value) if value else value
        self.endpoint = endpoint

    def json(self):
        d = self.__dict__
        d["endpoint"] = d["endpoint"].json() if d["endpoint"] else None
        return d


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
        d["endpoint"] = self.endpoint.json() if self.endpoint else None
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
            endpoint=Endpoint(url_for("wallets_endpoint.wallets_overview")),
        )

        sidebar_wallet = UIElement(
            html_wallets,
            ids=f"{wallet.alias}-sidebar-list-item",
            title=wallet.alias,
            endpoint=Endpoint(
                url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            ),
            search_function=lambda x: self._search_in_structure(
                x, {"name": wallet.alias}, title_key="name"
            ),
        )
        transactions = UIElement(
            sidebar_wallet,
            ids="btn_transactions",
            title="Transactions",
            endpoint=Endpoint(
                url_for("wallets_endpoint.history", wallet_alias=wallet.alias)
            ),
        )

        def transactions_history_generator():
            for tx in wallet.txlist():
                yield tx

        transactions_history = UIElement(
            transactions,
            ids=(
                f"tx-table-{wallet.alias}",
                "shadowRoot",
                "btn_history",
            ),
            title="History",
            endpoint=Endpoint(
                url_for(
                    "wallets_endpoint.history_tx_list_type",
                    wallet_alias=wallet.alias,
                    tx_list_type="txlist",
                )
            ),
            search_function=lambda x: self._search_in_structure(
                x, transactions_history_generator(), title_key="txid"
            ),
        )

        def transactions_utxo_generator():
            for utxo in wallet.full_utxo:
                yield utxo

        transactions_utxo = UIElement(
            transactions,
            ids=(
                f"tx-table-{wallet.alias}",
                "shadowRoot",
                "btn_utxo",
            ),
            title="UTXO",
            endpoint=Endpoint(
                url_for(
                    "wallets_endpoint.history_tx_list_type",
                    wallet_alias=wallet.alias,
                    tx_list_type="utxo",
                )
            ),
            search_function=lambda x: self._search_in_structure(
                x, transactions_utxo_generator(), title_key="txid"
            ),
        )

        addresses = UIElement(
            sidebar_wallet,
            ids="btn_addresses",
            title="Addresses",
            endpoint=Endpoint(
                url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias)
            ),
        )

        def addresses_recieve_generator(is_change):
            for address in wallet.addresses_info(is_change=is_change):
                yield address

        addresses_recieve = UIElement(
            addresses,
            ids=(
                f"addresses-table-{wallet.alias}",
                "shadowRoot",
                "receive-addresses-view-btn",
            ),
            title="Recieve Addresses",
            endpoint=Endpoint(
                url_for(
                    "wallets_endpoint.addresses_with_type",
                    wallet_alias=wallet.alias,
                    address_type="recieve",
                )
            ),
            search_function=lambda x: self._search_in_structure(
                x, addresses_recieve_generator(is_change=False), title_key="address"
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
            endpoint=Endpoint(
                url_for(
                    "wallets_endpoint.addresses_with_type",
                    wallet_alias=wallet.alias,
                    address_type="change",
                )
            ),
            search_function=lambda x: self._search_in_structure(
                x, addresses_recieve_generator(is_change=True), title_key="address"
            ),
        )

        recieve = UIElement(
            sidebar_wallet,
            ids="btn_receive",
            title="Recieve",
            endpoint=Endpoint(
                url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias)
            ),
            search_function=lambda x: self._search_in_structure(
                x, [wallet.address], title_key="address"
            ),
        )

        send = UIElement(
            sidebar_wallet,
            ids="btn_send",
            title="Send",
            endpoint=Endpoint(
                url_for("wallets_endpoint.send_new", wallet_alias=wallet.alias)
            ),
        )

        def unsigned_f_endpoint(psbt_dict):
            return Endpoint(
                url_for("wallets_endpoint.send_pending", wallet_alias=wallet.alias),
                method_str="form",
                form_data={
                    "action": "openpsbt",
                    "pending_psbt": json.dumps(psbt_dict),
                },
            )

        def unsigned_generator():
            for psbt in wallet.pending_psbts.values():
                psbt_dict = psbt.to_dict()
                psbt_dict["PSBT Address label"] = wallet.getlabel(
                    psbt_dict["address"][0]
                )
                yield psbt_dict

        unsigned = UIElement(
            send,
            ids="btn_send_pending",
            title="Unsigned",
            endpoint=Endpoint(
                url_for("wallets_endpoint.send_pending", wallet_alias=wallet.alias)
            ),
            search_function=lambda x: self._search_in_structure(
                x,
                unsigned_generator(),
                title_key="PSBT Address label",
                f_endpoint=unsigned_f_endpoint,
            ),
        )

    def _device_ui_elements(self, ui_root, device):
        html_devices = UIElement(
            ui_root,
            ids="toggle_devices_list",
            title="Devices",
            endpoint=Endpoint(url_for("wallets_endpoint.wallets_overview")),
        )

        sidebar_device = UIElement(
            html_devices,
            ids=f"device_list_item_{device.alias}",
            title=device.alias,
            endpoint=Endpoint(
                url_for("devices_endpoint.device", device_alias=device.alias)
            ),
            search_function=lambda x: self._search_in_structure(
                x, {"name": device.alias}, title_key="name"
            ),
        )

        def device_keys_generator():
            for key in device.keys:
                yield key

        device_keys = UIElement(
            sidebar_device,
            ids="keys-table-header-key",
            title="Keys",
            endpoint=Endpoint(
                url_for("devices_endpoint.device", device_alias=device.alias)
            ),
            search_function=lambda x: self._search_in_structure(
                x, device_keys_generator(), title_key="purpose"
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
        self,
        search_term,
        structure,
        title_key=None,
        f_endpoint=None,
        _result_meta_data=None,
    ):
        """
        Recursively goes through the list/tuple/set/GeneratorType until it hits a dict.
        It matches then the dict.values() with the search_term  (case insensitive)

        Args:
            search_term (str): A string (non-case-sensitive) which will be searched for in the structure
            structure (list, tuple, set, dict, types.GeneratorType):
                The structure should be non-static, meaning when the wallet information changes, the structure should be up-to-date.
                This can be achieved with directly pointing to wallet....  objects or generating a types.GeneratorType
                which uses wallet.... objects
            title_key (_type_, optional): If a result is found in a dictionary, then the value of the title_key
                is used as the title of the SearchResult, e.g,
                the title_key="txid" is the title of a search result in a tx-dictionary.
                Defaults to None.
            f_endpoint (_type_, optional): A function that takes the entire dict (which contains a search hit in some value)
                and returns an instance of type Endpoint.
                Defaults to None.
            _result_meta_data (_type_, optional): Only for internal purposes. Leave None

        Returns:
            results: list of SearchResult
        """

        def is_match(search_term, value):
            return search_term.lower() in str(value).lower()

        results = []
        if isinstance(structure, dict):
            for key, value in structure.items():
                if is_match(search_term, value):
                    endpoint = f_endpoint(structure) if f_endpoint else None
                    results += [
                        SearchResult(
                            value,
                            title=structure.get(title_key),
                            key=key,
                            endpoint=endpoint,
                        )
                    ]

        elif isinstance(structure, (types.GeneratorType, list, tuple, set)):
            for value in structure:
                update_dict = {"parent_structure": structure}
                if isinstance(_result_meta_data, dict):
                    _result_meta_data.update(update_dict)
                else:
                    _result_meta_data = update_dict

                results += self._search_in_structure(
                    search_term,
                    value,
                    title_key=title_key,
                    f_endpoint=f_endpoint,
                    _result_meta_data=_result_meta_data,
                )
        else:
            # if it is not a list,dict,... then it is the final element that should be searched:
            if is_match(search_term, structure):
                endpoint = f_endpoint(structure) if f_endpoint else None
                results += [
                    SearchResult(
                        structure,
                        endpoint=endpoint,
                    )
                ]

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
