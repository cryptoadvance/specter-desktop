import logging

from cryptoadvance.specter.services.service import (
    Service,
    devstatus_alpha,
    devstatus_prod,
    devstatus_beta,
)

# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from flask import render_template
from cryptoadvance.specter.wallet import Wallet
from flask_apscheduler import APScheduler
from .notification_manager import NotificationManager
from .current_flask_user import flash

logger = logging.getLogger(__name__)


class NotificationsService(Service):
    id = "notifications"
    name = "Notifications Service"
    icon = "notifications/img/ghost.png"
    logo = "notifications/img/logo.jpeg"
    desc = "Where a notifications grows bigger."
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.notifications.controller"
    devices = ["cryptoadvance.specterext.notifications.devices."]
    devstatus = devstatus_prod
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    # ServiceEncryptedStorage field names for this service
    # Those will end up as keys in a json-file
    SPECTER_WALLET_ALIAS = "wallet"

    def callback_after_serverpy_init_app(self, scheduler: APScheduler, app):
        def every5seconds(hello, world="world"):
            with scheduler.app.app_context():
                print(f"Called {hello} {world} every5seconds")

        # Here you can schedule regular jobs. triggers can be one of "interval", "date" or "cron"
        # Examples:
        # interval: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html
        # scheduler.add_job("every5seconds4", every5seconds, trigger='interval', seconds=5, args=["hello"])

        # Date: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/date.html
        # scheduler.add_job("MyId", my_job, trigger='date', run_date=date(2009, 11, 6), args=['text'])

        # cron: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html
        # sched.add_job("anotherID", job_function, trigger='cron', day_of_week='mon-fri', hour=5, minute=30, end_date='2014-05-30')

        # Maybe you should store the scheduler for later use:
        self.scheduler = scheduler

        self.notification_manager = NotificationManager(
            app.config.get("host", "127.0.0.1"),
            app.config["PORT"],
            app.config["CERT"],
            app.config["KEY"],
        )
        for user in app.specter.user_manager.users:
            self.notification_manager.register_user_ui_notifications(user.id)

        self.flash = flash

    # There might be other callbacks you're interested in. Check the callbacks.py in the specter-desktop source.
    # if you are, create a method here which is "callback_" + callback_id

    @classmethod
    def get_associated_wallet(cls) -> Wallet:
        """Get the Specter `Wallet` that is currently associated with this service"""
        service_data = cls.get_current_user_service_data()
        if not service_data or cls.SPECTER_WALLET_ALIAS not in service_data:
            # Service is not initialized; nothing to do
            return
        try:
            return app.specter.wallet_manager.get_by_alias(
                service_data[cls.SPECTER_WALLET_ALIAS]
            )
        except SpecterError as e:
            logger.debug(e)
            # Referenced an unknown wallet
            # TODO: keep ignoring or remove the unknown wallet from service_data?
            return

    @classmethod
    def set_associated_wallet(cls, wallet: Wallet):
        """Set the Specter `Wallet` that is currently associated with this Service"""
        cls.update_current_user_service_data({cls.SPECTER_WALLET_ALIAS: wallet.alias})

    @classmethod
    def inject_in_basejinja_body_top(cls):
        return render_template("notifications/html_inject_in_basejinja.jinja")
