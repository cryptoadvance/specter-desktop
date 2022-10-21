import logging
import os
import sys
from importlib import import_module

from flask import current_app as app
from flask.blueprints import Blueprint
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.util.reflection import get_template_static_folder
from flask_babel import lazy_gettext as _
from typing import List

from .service_encrypted_storage import ServiceEncryptedStorageManager
from .service_annotations_storage import ServiceAnnotationsStorage

from cryptoadvance.specter.addresslist import Address
from cryptoadvance.specter.services import callbacks


logger = logging.getLogger(__name__)


devstatus_alpha = "alpha"
devstatus_beta = "beta"
devstatus_prod = "prod"


class Service:
    """A base class for Services"""

    # These should be overrided in implementation classes
    id = None
    name = None
    icon = None
    logo = None
    desc = None  # TODO: rename to "description" to be explicit
    has_blueprint = True  # the default
    # If the blueprint gets a "/ext" prefix (isolated_client = True), the login cookie won't work for all specter core functionality
    isolated_client = True
    devstatus = devstatus_alpha
    encrypt_data = False

    def __init__(self, active, specter, storage_manager):
        if not hasattr(self, "id"):
            raise Exception(f"Service {self.__class__} needs ID")
        if not hasattr(self, "name"):
            raise Exception(f"Service {self.__class__} needs name")
        self.active = active
        self.specter = specter

        # ensure that an encrypted storage manager is passed
        if self.encrypt_data:
            assert isinstance(storage_manager, ServiceEncryptedStorageManager)
        self.storage_manager = storage_manager

    def callback(self, callback_id, *argv, **kwargv):
        if callback_id == callbacks.after_serverpy_init_app:
            if hasattr(self, "callback_after_serverpy_init_app"):
                self.callback_after_serverpy_init_app(kwargv["scheduler"])

    def set_current_user_service_data(self, service_data: dict):
        self.storage_manager.set_current_user_service_data(
            service_id=self.id, service_data=service_data
        )

    def update_current_user_service_data(self, service_data: dict):
        self._storage_manager().update_current_user_service_data(
            service_id=self.id, service_data=service_data
        )

    def get_current_user_service_data(self) -> dict:
        return self._storage_manager().get_current_user_service_data(service_id=self.id)

    def get_blueprint_name(self):
        return f"{self.id}_endpoint"

    def default_address_label(cls):
        # Have to str() it; can't pass a LazyString to json serializer
        return str(_("Reserved for {}").format(self.name))

    def reserve_address(self, wallet: Wallet, address: str, label: str = None):
        # Mark an Address in a persistent way as being reserved by a Service
        if not label:
            label = self.default_address_label()
        wallet.associate_address_with_service(
            address=address, service_id=self.id, label=label
        )

    def reserve_addresses(
        self,
        wallet: Wallet,
        label: str = None,
        num_addresses: int = 10,
        annotations: dict = None,
    ) -> List[str]:
        """
        Reserve n unused addresses but leave a gap between each one so that this reserved
        range never causes an address gap in the wallet (e.g. if you reserve ten in a
        row it's possible that some wallet software will miss a new tx on the 11th
        address).

        If `label` is not provided, we use Service.default_address_label().

        Optional `annotations` data can be attached to each Address being reserved.
        """
        # Track Service-related addresses in ServiceAnnotationsStorage
        if annotations:
            annotations_storage = ServiceAnnotationsStorage(
                service_id=self.id, wallet=wallet
            )

        # Start with the addresses that are already reserved but still unused
        addresses: List[str] = wallet.get_associated_addresses(
            service_id=self.id, unused_only=True
        )
        logger.debug(f"Already have {len(addresses)} addresses reserved for {self.id}")

        if len(addresses) < num_addresses:
            if addresses:
                # Continuing reserving from where we left off
                index = addresses[-1].index + 2

                # Final `addresses` list has to be just addr strs
                addresses = [addr_obj.address for addr_obj in addresses]
            else:
                index = wallet.address_index + 1

            while len(addresses) < num_addresses:
                address = wallet.get_address(index)
                addr_obj = wallet.get_address_obj(address)

                index += 2

                if addr_obj.used or addr_obj.is_reserved:
                    continue

                # Mark an Address in a persistent way as being reserved by a Service
                self.reserve_address(wallet=wallet, address=address)
                logger.debug(f"Reserved {address} for {self.id}")

                addresses.append(address)

                if annotations:
                    annotations_storage.set_addr_annotations(
                        addr=address, annotations=annotations, autosave=False
                    )
        if annotations:
            annotations_storage.save()

        return addresses

    def unreserve_addresses(self, wallet: Wallet):
        """
        Clear out Services-related data from any unused Addresses, but leave already-used
        Addresses as-is.
        """
        annotations_storage = ServiceAnnotationsStorage(
            service_id=self.id, wallet=wallet
        )
        addrs = wallet.get_associated_addresses(service_id=self.id, unused_only=True)
        for addr_obj in addrs:
            wallet.deassociate_address(addr_obj["address"])
            annotations_storage.remove_addr_annotations(
                addr_obj.address, autosave=False
            )
        annotations_storage.save()

    # def is_active(self):
    #     return self.active

    # def set_active(self, value):
    #     self.active = value

    def update(self):
        """
        Called by backend periodic process to keep Service in sync with any remote
        data (e.g. fetching the latest data from an external API).
        """
        logger.info(f"update() not implemented / not necessary for Service {self.id}")

    """ ***********************************************************************
                                    Update hooks
    *********************************************************************** """

    def on_user_login(cls):
        pass

    def inject_in_basejinja_head(cls):
        """overwrite this method to inject a snippet of code in specter's base.jinja
        the snippet will be placed at the end of the head-section
        a typical implementation would be something like:
        return render_template("myext/inject_in_basejinja_head.jinja")
        """
        pass

    def inject_in_basejinja_body_top(cls):
        """overwrite this method to inject a snippet of code in specter's base.jinja
        the snippet will be placed at the top of the body-section
        a typical implementation would be something like:
        return render_template("myext/inject_in_basejinja_body_top.jinja")
        """
        pass

    def inject_in_basejinja_body_bottom(cls):
        """overwrite this method to inject a snippet of code in specter's base.jinja
        the snippet will be placed at the top of the body-section
        a typical implementation would be something like:
        return render_template("myext/inject_in_basejinja_body_bottom.jinja")
        """
        pass
