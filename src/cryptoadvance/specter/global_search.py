from locale import LC_TIME
import os
import logging, json
import types
from flask import url_for
from flask_babel import lazy_gettext as _
from .util.common import robust_json_dumps
from datetime import datetime
from babel.dates import format_datetime

logger = logging.getLogger(__name__)


class ClickAction:
    """This contains the information to describe what should happen after a click.
    In the simple case this is just an url for a link/href.
    It can also be a form submission to the url.
    """

    def __init__(self, url, method_str="href", form_data=None):
        """
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
    """
    Contains all information for 1 single search result
    """

    def __init__(self, value, title=None, key=None, click_action=None) -> None:
        """
        Args:
            value (any): E.g. the string in which the search_term was found
            title (str, optional): The title of the search result, e.g. the "Address #2". Defaults to None.
            key (str, optional): E.g. "Blockhash", meaning the search_term was found in the blockhash. Defaults to None.
            click_action (ClickAction, optional): An instance of type ClickAction. Defaults to None.
        """
        self.value = str(value) if value else value
        self.title = str(title) if title else title
        self.key = str(key).capitalize() if key else key
        self.click_action = click_action

    def json(self):
        d = self.__dict__
        d["click_action"] = d["click_action"].json() if d["click_action"] else None
        return d


class SearchableCategory:
    def __init__(
        self,
        structure_or_generator_function,
        title_function=None,
        click_action_function=None,
        locale=None,
    ) -> None:
        """
        Args:
            structure_or_generator_function (list, tuple, set, dict, returning types.GeneratorType, or function returning formers):
                The structure_or_generator_function should be non-static, meaning when the wallet information changes, the structure_or_generator_function should be up-to-date.
                This can be achieved with a function that returns an iterable
            title_function (function, optional): A function that takes the entire dict (which contains a search hit in some value)
                and returns a string, which is used as the title of the SearchResult, e.g,
                title_function = lambda d: d.get("txid").
                Defaults to None.
            click_action_function (_type_, optional): A function that takes the entire dict (which contains a search hit in some value)
                and returns an instance of type ClickAction.
                Defaults to None.
            locale (str or `Locale` object, optional): a `Locale` object or a locale identifier, e.g. 'en_US'
        """
        self.structure_or_generator_function = structure_or_generator_function
        self.title_function = title_function
        self.click_action_function = click_action_function
        self.locale = locale

    def search(
        self,
        search_term,
        structure=None,
        _result_meta_data=None,
    ):
        """
        Recursively goes through the list/tuple/set/types.GeneratorType until it hits a dict.
        It matches then the dict.values() with the search_term  (case insensitive)

        Args:
            search_term (str): A string (non-case-sensitive) which will be searched for in the structure
            structure_or_generator_function (list, tuple, set, dict, returning types.GeneratorType, or function returning formers):
            _result_meta_data (_type_, optional): Only for internal purposes. Leave None

        Returns:
            results: list of SearchResult
        """
        if structure is None:
            structure = self.structure_or_generator_function
        if callable(structure):
            structure = structure()

        def get_search_hit(search_term, value, key=None):
            # for dates search additionally the formatted date_time
            if key in ["time", "blocktime"] and isinstance(value, (int, float)):
                kwargs = {"locale": self.locale} if self.locale else {}
                date_time_value = format_datetime(
                    datetime.fromtimestamp(value), **kwargs
                )
                found = search_term.lower() in str(date_time_value).lower()
                if found:
                    return date_time_value

            found = search_term.lower() in str(value).lower()
            return value if found else None

        results = []
        if isinstance(structure, dict):
            for key, value in structure.items():
                search_hit = get_search_hit(search_term, value, key=key)
                if search_hit:
                    result = SearchResult(
                        search_hit,
                        title=self.title_function(structure),
                        key=key,
                        click_action=self.click_action_function(structure)
                        if self.click_action_function
                        else None,
                    )
                    # avoid duplicate results
                    if result not in results:
                        results.append(result)

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
            # if it is not a list,dict,... then it is the final element, e.g., a string, that should be searched:
            search_hit = get_search_hit(search_term, structure)
            if search_hit:
                result = SearchResult(
                    search_hit,
                    click_action=self.click_action_function(structure)
                    if self.click_action_function
                    else None,
                )
                # avoid duplicate results
                if result not in results:
                    results.append(result)

        return results


class UIElement:
    """
    This is a logical struture representing an UI/enpoint/HTML element, e.g., a button, a tab, with at most 1 search function accociated.
    E.g. the "Change Addresses" tab would be 1 UIElement

    Multiple of these elements can be attached to each other, by referencing the parent element during __init__, building a tree
    This tree is not a full reconstruction of the HTML DOM tree, but only the most necessary part to represent the logical structure
    the user sees as "Wallets > my multisig wallet > UTXOs" labeling all results found by the SearchableCategory.
    """

    def __init__(
        self,
        parent,
        title,
        click_action,
        searchable_category=None,
        children=None,
    ):
        """

        Args:
            parent (UIElement, None):
            title (str): The title, e.g. "Receive Addresses"
            click_action (str): e.g. url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)
            searchable_category (_type_, optional): If this UIElement should be searchable (usually then it should not have children)
                            then an instance of SearchableCategory can be linked. Defaults to None.
            children (set of UIElement, optional): A set of UIElements. This is usually not necessary to set, because any child linking
                        to this as a parent will automatically add itself in this set. Defaults to None.
        """
        self.parent = parent
        if self.parent:
            self.parent.children.add(self)
        self.title = title
        self.click_action = click_action
        self.searchable_category = searchable_category
        self.children = children if children else set()

    def nodes_with_searchable_category(self):
        "Typically the nodes having a search_function, are childless nodes."
        nodes = []
        if self.searchable_category:
            nodes += [self]

        for child in self.children:
            nodes += child.nodes_with_searchable_category()
        return nodes

    def flattened_parent_list(self):
        parents = []
        if self.parent:
            parents = self.parent.flattened_parent_list() + [self.parent]

        return parents

    def json(self, include_flattened_parent_list=False):
        d = {}
        if include_flattened_parent_list:
            d["flattened_parent_list"] = [
                parent.json() for parent in self.flattened_parent_list()
            ]
        d["title"] = self.title
        d["click_action"] = self.click_action.json() if self.click_action else None
        return d


class GlobalSearchTree:
    "Builds the Ui Tree and holds the different UI roots of different users"

    def __init__(self):
        self.cache = {}

    def _wallet_ui_elements(self, ui_root, wallet, hide_sensitive_info, locale=None):
        html_wallets = UIElement(
            ui_root,
            _("Wallets"),
            ClickAction(url_for("wallets_endpoint.wallets_overview")),
        )

        sidebar_wallet_searchable_category = SearchableCategory(
            {"alias": wallet.alias, "name": wallet.name},
            title_function=lambda d: d.get("name"),
            locale=locale,
        )
        sidebar_wallet = UIElement(
            html_wallets,
            wallet.name,
            ClickAction(url_for("wallets_endpoint.wallet", wallet_alias=wallet.alias)),
            searchable_category=sidebar_wallet_searchable_category,
        )

        transactions = UIElement(
            sidebar_wallet,
            _("Transactions"),
            ClickAction(url_for("wallets_endpoint.history", wallet_alias=wallet.alias)),
        )

        def transactions_history_generator():
            for tx in wallet.txlist():
                yield tx

        def tx_click_action_function(tx_dict, tx_list_type):
            return ClickAction(
                url_for(
                    "wallets_endpoint.history_tx_list_type",
                    wallet_alias=wallet.alias,
                    tx_list_type=tx_list_type,
                ),
                method_str="form",
                form_data={
                    "action": "show_tx_on_load",
                    "txid": tx_dict["txid"],
                },
            )

        transactions_history_searchable_category = SearchableCategory(
            transactions_history_generator,
            title_function=lambda d: d.get("txid"),
            click_action_function=lambda tx_dict: tx_click_action_function(
                tx_dict, "txlist"
            ),
            locale=locale,
        )
        if not hide_sensitive_info:
            transactions_history = UIElement(
                transactions,
                _("History"),
                ClickAction(
                    url_for(
                        "wallets_endpoint.history_tx_list_type",
                        wallet_alias=wallet.alias,
                        tx_list_type="txlist",
                    )
                ),
                searchable_category=transactions_history_searchable_category,
            )

        def transactions_utxo_generator():
            for utxo in wallet.full_utxo:
                yield utxo

        transactions_utxo_searchable_category = SearchableCategory(
            transactions_utxo_generator,
            title_function=lambda d: d.get("txid"),
            click_action_function=lambda tx_dict: tx_click_action_function(
                tx_dict, "utxo"
            ),
            locale=locale,
        )
        if not hide_sensitive_info:
            transactions_utxo = UIElement(
                transactions,
                _("UTXO"),
                ClickAction(
                    url_for(
                        "wallets_endpoint.history_tx_list_type",
                        wallet_alias=wallet.alias,
                        tx_list_type="utxo",
                    )
                ),
                searchable_category=transactions_utxo_searchable_category,
            )

        addresses = UIElement(
            sidebar_wallet,
            _("Addresses"),
            ClickAction(
                url_for("wallets_endpoint.addresses", wallet_alias=wallet.alias)
            ),
        )

        def addresses_receive_generator(is_change):
            for address in wallet.addresses_info(is_change=is_change):
                yield address

        def address_receive_click_action_function(address_dict, address_type):
            return ClickAction(
                url_for(
                    "wallets_endpoint.addresses_with_type",
                    wallet_alias=wallet.alias,
                    address_type=address_type,
                ),
                method_str="form",
                form_data={
                    "action": "show_address_on_load",
                    "address_dict": robust_json_dumps(address_dict),
                },
            )

        addresses_receive_searchable_category = SearchableCategory(
            lambda: addresses_receive_generator(is_change=False),
            title_function=lambda d: d.get("label"),
            click_action_function=lambda address_dict: address_receive_click_action_function(
                address_dict, "receive"
            ),
            locale=locale,
        )
        if not hide_sensitive_info:
            addresses_receive = UIElement(
                addresses,
                _("Receive Addresses"),
                ClickAction(
                    url_for(
                        "wallets_endpoint.addresses_with_type",
                        wallet_alias=wallet.alias,
                        address_type="receive",
                    )
                ),
                searchable_category=addresses_receive_searchable_category,
            )

        addresses_change_searchable_category = SearchableCategory(
            lambda: addresses_receive_generator(is_change=True),
            title_function=lambda d: d.get("label"),
            click_action_function=lambda address_dict: address_receive_click_action_function(
                address_dict, "change"
            ),
            locale=locale,
        )
        if not hide_sensitive_info:
            addresses_change = UIElement(
                addresses,
                _("Change Addresses"),
                ClickAction(
                    url_for(
                        "wallets_endpoint.addresses_with_type",
                        wallet_alias=wallet.alias,
                        address_type="change",
                    )
                ),
                searchable_category=addresses_change_searchable_category,
            )

        receive_searchable_category = SearchableCategory(
            {"address": wallet.address, "label": wallet.getlabel(wallet.address)},
            title_function=lambda d: d.get("label"),
            locale=locale,
        )
        receive = UIElement(
            sidebar_wallet,
            _("Receive"),
            ClickAction(url_for("wallets_endpoint.receive", wallet_alias=wallet.alias)),
            searchable_category=receive_searchable_category,
        )

        if not hide_sensitive_info:
            send = UIElement(
                sidebar_wallet,
                _("Send"),
                ClickAction(
                    url_for("wallets_endpoint.send_new", wallet_alias=wallet.alias)
                ),
            )

        def unsigned_click_action_function(psbt_dict):
            return ClickAction(
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

        unsigned_searchable_category = SearchableCategory(
            unsigned_generator,
            title_function=lambda d: d.get("PSBT Address label"),
            click_action_function=unsigned_click_action_function,
            locale=locale,
        )
        if not hide_sensitive_info:
            unsigned = UIElement(
                send,
                _("Unsigned"),
                ClickAction(
                    url_for("wallets_endpoint.send_pending", wallet_alias=wallet.alias)
                ),
                searchable_category=unsigned_searchable_category,
            )

    def _device_ui_elements(self, ui_root, device, hide_sensitive_info, locale=None):
        html_devices = UIElement(
            ui_root,
            _("Devices"),
            ClickAction(url_for("wallets_endpoint.wallets_overview")),
        )

        sidebar_device_searchable_category = SearchableCategory(
            {"alias": device.alias, "name": device.name},
            title_function=lambda d: d.get("name"),
            locale=locale,
        )
        sidebar_device = UIElement(
            html_devices,
            device.name,
            ClickAction(url_for("devices_endpoint.device", device_alias=device.alias)),
            searchable_category=sidebar_device_searchable_category,
        )

        def device_keys_generator():
            for key in device.keys:
                yield key

        device_keys_searchable_category = SearchableCategory(
            device_keys_generator,
            title_function=lambda d: d.get("purpose"),
            locale=locale,
        )
        if not hide_sensitive_info:
            device_keys = UIElement(
                sidebar_device,
                _("Keys"),
                ClickAction(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                ),
                searchable_category=device_keys_searchable_category,
            )

    def _build_ui_elements(self, user_config):
        """
        This builds all UIElements that should be highlighted during a search.
        It also encodes which functions will be used for searching.

        Returns:
            UIElement: This is the ui_root, which has all children linked in a tree
        """
        ui_root = UIElement(None, "root", ClickAction(url_for("setup_endpoint.start")))
        for wallet in user_config["wallets"]:
            self._wallet_ui_elements(
                ui_root,
                wallet,
                user_config["hide_sensitive_info"],
                locale=user_config["locale"],
            )
        for device in user_config["devices"]:
            self._device_ui_elements(
                ui_root, device, user_config["hide_sensitive_info"]
            )
        return ui_root

    def _search_in_ui_element(self, search_term, ui_root):
        """
        Searches all nodes, which have a searchable_category

        Args:
            search_term (_type_): _description_
            ui_root (_type_): _description_

        Returns:
            list of dict: Example:
                [{
                    'ui_element': {
                        'flattened_parent_list': [{
                            'flattened_parent_list': [],
                            'title': None,
                            'click_action': None
                        }],
                        'title': 'History',
                        'click_action': '/wallets/wallet/tr/history/txlist/'
                    },
                    'search_results': [{
                        'title': '599a2780545f456b69feac58a1e4ef8271a81a367c08315cffd3e91e2e23f95a',
                        'key': 'Blockhash',
                        'value': '65dc072035e1f870963a111a188e14a7359454b02a09210ead68250a051f6b16'
                    }]
                }]
        """
        result_dicts = []
        for node in ui_root.nodes_with_searchable_category():
            result_dict = {
                "ui_element": node.json(include_flattened_parent_list=True),
                "search_results": [
                    hit.json() for hit in node.searchable_category.search(search_term)
                ],
            }
            if result_dict["search_results"]:
                result_dicts.append(result_dict)
        return result_dicts

    def user_config(self, hide_sensitive_info, wallets, devices, locale):
        """A minimalist version of building a user configuration,
        that if changed shows that the UI Tree needs to be rebuild"""
        return {
            "hide_sensitive_info": hide_sensitive_info,
            "wallets": wallets,
            "devices": devices,
            "locale": locale,
        }

    def do_global_search(
        self,
        search_term,
        user_id,
        hide_sensitive_info,
        wallets,
        devices,
        locale=None,
        force_build_ui_tree=False,
    ):
        "Builds the UI Tree if non-existent, or it the config changed and then calls the functions in it to search for the search_term"
        user_config = self.user_config(
            hide_sensitive_info,
            list(wallets.values()),
            list(devices.values()),
            locale,
        )
        if (
            force_build_ui_tree
            or (user_id not in self.cache)
            or self.cache[user_id]["user_config"] != user_config
        ):
            logger.debug(
                f'Building GlobalSearchTree for user {user_id} with {len(user_config["wallets"])} wallets and {len(user_config["devices"])} devices'
            )
            self.cache[user_id] = {
                "user_config": user_config,
                "ui_root": self._build_ui_elements(user_config),
            }

        result_dicts = (
            self._search_in_ui_element(search_term, self.cache[user_id]["ui_root"])
            if len(search_term) > 1
            else []
        )

        return {
            "result_dicts": result_dicts,
            "search_term": search_term,
        }
