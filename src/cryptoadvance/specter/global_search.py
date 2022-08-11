import os
import logging, json
import types
from flask import url_for
from .util.common import robust_json_dumps

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
        self.value = str(value) if value else value
        self.title = str(title) if title else title
        self.key = str(key).capitalize() if key else key
        self.endpoint = endpoint

    def json(self):
        d = self.__dict__
        d["endpoint"] = d["endpoint"].json() if d["endpoint"] else None
        return d


class SearchableStructure:
    def __init__(
        self, structure_or_generator_function, title_key=None, endpoint_function=None
    ) -> None:
        """_summary_

        Args:
            structure_or_generator_function (list, tuple, set, dict, types.GeneratorType function):
                The structure_or_generator_function should be non-static, meaning when the wallet information changes, the structure_or_generator_function should be up-to-date.
                This can be achieved with directly pointing to wallet....  objects or generating a types.GeneratorType
                which uses wallet.... objects
            title_key (_type_, optional): If a result is found in a dictionary, then the value of the title_key
                is used as the title of the SearchResult, e.g,
                the title_key="txid" is the title of a search result in a tx-dictionary.
                Defaults to None.
            endpoint_function (_type_, optional): A function that takes the entire dict (which contains a search hit in some value)
                and returns an instance of type Endpoint.
                Defaults to None.
        """
        self.structure_or_generator_function = structure_or_generator_function
        self.title_key = title_key
        self.endpoint_function = endpoint_function

    def search(
        self,
        search_term,
        structure=None,
        _result_meta_data=None,
    ):
        """
        Recursively goes through the list/tuple/set/types.GeneratorType function until it hits a dict.
        It matches then the dict.values() with the search_term  (case insensitive)

        Args:
            search_term (str): A string (non-case-sensitive) which will be searched for in the structure
            _result_meta_data (_type_, optional): Only for internal purposes. Leave None

        Returns:
            results: list of SearchResult
        """
        if structure is None:
            structure = self.structure_or_generator_function
        if callable(structure):
            structure = structure()

        def is_match(search_term, value):
            return search_term.lower() in str(value).lower()

        results = []
        if isinstance(structure, dict):
            for key, value in structure.items():
                if is_match(search_term, value):
                    results += [
                        SearchResult(
                            value,
                            title=structure.get(self.title_key),
                            key=key,
                            endpoint=self.endpoint_function(structure)
                            if self.endpoint_function
                            else None,
                        )
                    ]

        elif isinstance(structure, (types.GeneratorType, list, tuple, set)):
            for value in structure:
                update_dict = {"parent_structure": structure}
                if isinstance(_result_meta_data, dict):
                    _result_meta_data.update(update_dict)
                else:
                    _result_meta_data = update_dict

                results += self.search(
                    search_term,
                    structure=value,
                    _result_meta_data=_result_meta_data,
                )
        else:
            # if it is not a list,dict,... then it is the final element that should be searched:
            if is_match(search_term, structure):
                results += [
                    SearchResult(
                        structure,
                        endpoint=self.endpoint_function(structure)
                        if self.endpoint_function
                        else None,
                    )
                ]

        return results


class UIElement:
    """
    This is a logical struture representing an UI/enpoint/HTML element, e.g., a button, a tab, with at most 1 search function accociated.
    E.g. the "Change Addresses" tab would be 1 UIElement

    Multiple of these elements can be attached to each other, by referencing the parent element during __init__

    This is not a full reconstruction of the HTML DOM tree, but only the most necessary part to represent the logical structure
    the user sees. And only these parts which are included in the search.
    """

    def __init__(
        self,
        parent,
        title,
        endpoint,
        searchable_structure=None,
        children=None,
    ):
        """

        Args:
            parent (UIElement, None): _description_
            title (str): _description_
            endpoint (str): _description_
            searchable_structure (_type_, optional): _description_. Defaults to None.
            children (UIElement, optional): _description_. Defaults to None.
        """
        self.parent = parent
        if self.parent:
            self.parent.children.add(self)
        self.title = title
        self.endpoint = endpoint
        self.searchable_structure = searchable_structure
        self.children = children if children else set()

    def nodes_with_searchable_structure(self):
        "Typically the nodes having a search_function, are childless nodes."
        nodes = []
        if self.searchable_structure:
            nodes += [self]

        for child in self.children:
            nodes += child.nodes_with_searchable_structure()
        return nodes

    def flattened_parent_list(self):
        parents = []
        if self.parent:
            parents = self.parent.flattened_parent_list() + [self.parent]

        return parents

    def json(self):
        d = {}
        d["flattened_parent_list"] = [
            parent.json() for parent in self.flattened_parent_list()
        ]
        d["title"] = self.title
        d["endpoint"] = self.endpoint.json() if self.endpoint else None
        return d


class GlobalSearchTrees:
    "builds the Ui Tree and holds the different UI roots of different users"

    def __init__(self):
        self.ui_roots = {}

    def _wallet_ui_elements(self, ui_root, wallet):
        html_wallets = UIElement(
            ui_root,
            "Wallets",
            Endpoint(url_for("wallets_endpoint.wallets_overview")),
        )

        sidebar_wallet_searchable_structure = SearchableStructure(
            {"name": wallet.alias}, title_key="name"
        )
        sidebar_wallet = UIElement(
            html_wallets,
            wallet.alias,
            Endpoint(url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)),
            searchable_structure=sidebar_wallet_searchable_structure,
        )

        transactions = UIElement(
            sidebar_wallet,
            "Transactions",
            Endpoint(url_for("wallets_endpoint.history", wallet_alias=wallet.alias)),
        )

        def transactions_history_generator():
            for tx in wallet.txlist():
                yield tx

        def tx_endpoint_function(tx_dict, tx_list_type):
            return Endpoint(
                url_for(
                    "wallets_endpoint.history_tx_list_type",
                    wallet_alias=wallet.alias,
                    tx_list_type=tx_list_type,
                ),
                method_str="form",
                form_data={
                    "action": "open_tx_at_load",
                    "txid": tx_dict["txid"],
                },
            )

        transactions_history_searchable_structure = SearchableStructure(
            transactions_history_generator,
            title_key="txid",
            endpoint_function=lambda tx_dict: tx_endpoint_function(tx_dict, "txlist"),
        )
        transactions_history = UIElement(
            transactions,
            "History",
            Endpoint(
                url_for(
                    "wallets_endpoint.history_tx_list_type",
                    wallet_alias=wallet.alias,
                    tx_list_type="txlist",
                )
            ),
            searchable_structure=transactions_history_searchable_structure,
        )

        def transactions_utxo_generator():
            for utxo in wallet.full_utxo:
                yield utxo

        transactions_utxo_searchable_structure = SearchableStructure(
            transactions_utxo_generator,
            title_key="txid",
            endpoint_function=lambda tx_dict: tx_endpoint_function(tx_dict, "utxo"),
        )
        transactions_utxo = UIElement(
            transactions,
            "UTXO",
            Endpoint(
                url_for(
                    "wallets_endpoint.history_tx_list_type",
                    wallet_alias=wallet.alias,
                    tx_list_type="utxo",
                )
            ),
            searchable_structure=transactions_utxo_searchable_structure,
        )

        addresses = UIElement(
            sidebar_wallet,
            "Addresses",
            Endpoint(url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias)),
        )

        def addresses_recieve_generator(is_change):
            for address in wallet.addresses_info(is_change=is_change):
                yield address

        def address_recieve_endpoint_function(address_dict, address_type):
            return Endpoint(
                url_for(
                    "wallets_endpoint.addresses_with_type",
                    wallet_alias=wallet.alias,
                    address_type=address_type,
                ),
                method_str="form",
                form_data={
                    "action": "open_at_load_address_json",
                    "address_dict": robust_json_dumps(address_dict),
                },
            )

        addresses_recieve_searchable_structure = SearchableStructure(
            lambda: addresses_recieve_generator(is_change=False),
            title_key="address",
            endpoint_function=lambda address_dict: address_recieve_endpoint_function(
                address_dict, "recieve"
            ),
        )
        addresses_recieve = UIElement(
            addresses,
            "Recieve Addresses",
            Endpoint(
                url_for(
                    "wallets_endpoint.addresses_with_type",
                    wallet_alias=wallet.alias,
                    address_type="recieve",
                )
            ),
            searchable_structure=addresses_recieve_searchable_structure,
        )

        addresses_change_searchable_structure = SearchableStructure(
            lambda: addresses_recieve_generator(is_change=True),
            title_key="address",
            endpoint_function=lambda address_dict: address_recieve_endpoint_function(
                address_dict, "change"
            ),
        )
        addresses_change = UIElement(
            addresses,
            "Change Addresses",
            Endpoint(
                url_for(
                    "wallets_endpoint.addresses_with_type",
                    wallet_alias=wallet.alias,
                    address_type="change",
                )
            ),
            searchable_structure=addresses_change_searchable_structure,
        )

        recieve_searchable_structure = SearchableStructure(
            [wallet.address], title_key="address"
        )
        recieve = UIElement(
            sidebar_wallet,
            "Recieve",
            Endpoint(url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias)),
            searchable_structure=recieve_searchable_structure,
        )

        send = UIElement(
            sidebar_wallet,
            "Send",
            Endpoint(url_for("wallets_endpoint.send_new", wallet_alias=wallet.alias)),
        )

        def unsigned_endpoint_function(psbt_dict):
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

        unsigned_searchable_structure = SearchableStructure(
            unsigned_generator,
            title_key="PSBT Address label",
            endpoint_function=unsigned_endpoint_function,
        )
        unsigned = UIElement(
            send,
            "Unsigned",
            Endpoint(
                url_for("wallets_endpoint.send_pending", wallet_alias=wallet.alias)
            ),
            searchable_structure=unsigned_searchable_structure,
        )

    def _device_ui_elements(self, ui_root, device):
        html_devices = UIElement(
            ui_root,
            "Devices",
            Endpoint(url_for("wallets_endpoint.wallets_overview")),
        )

        sidebar_device_searchable_structure = SearchableStructure(
            {"name": device.alias}, title_key="name"
        )
        sidebar_device = UIElement(
            html_devices,
            device.alias,
            Endpoint(url_for("devices_endpoint.device", device_alias=device.alias)),
            searchable_structure=sidebar_device_searchable_structure,
        )

        def device_keys_generator():
            for key in device.keys:
                yield key

        device_keys_searchable_structure = SearchableStructure(
            device_keys_generator, title_key="purpose"
        )
        device_keys = UIElement(
            sidebar_device,
            "Keys",
            Endpoint(url_for("devices_endpoint.device", device_alias=device.alias)),
            searchable_structure=device_keys_searchable_structure,
        )

    def _build_ui_elements(self, wallet_manager, device_manager):
        """
        This builds all UIElements that should be highlighted during a search.
        It also encodes which functions will be used for searching.

        Returns:
            UIElement: This is the html_root, which has all children linked in a tree
        """
        ui_root = UIElement(None, "root", Endpoint(url_for("setup_endpoint.start")))
        for wallet in wallet_manager.wallets.values():
            self._wallet_ui_elements(ui_root, wallet)
        for device in device_manager.devices.values():
            self._device_ui_elements(ui_root, device)
        return ui_root

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
                        'flattened_parent_list': [{
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
        for node in html_root.nodes_with_searchable_structure():
            result_dict = {
                "ui_element": node.json(),
                "search_hits": [
                    hit.json() for hit in node.searchable_structure.search(search_term)
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
