import logging

from cryptoadvance.specter.services.service import (
    Service,
    devstatus_alpha,
    devstatus_prod,
    devstatus_beta,
    ServiceOptionality,
)

# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import render_template
from cryptoadvance.specter.wallet import Wallet
from flask_apscheduler import APScheduler
from .notification_manager import NotificationManager
from flask_login import current_user, AnonymousUserMixin

logger = logging.getLogger(__name__)


class NotificationsService(Service):
    id = "notifications"
    name = "Notifications Service"
    icon = "notifications/img/notification.png"
    logo = "notifications/img/notification.png"
    desc = "Where a notifications grows bigger."
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.notifications.controller"
    devstatus = devstatus_alpha
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2
    optionality = ServiceOptionality.opt_in
    visible_in_sidebar = False

    def callback_after_serverpy_init_app(self, scheduler: APScheduler):
        """
        Args:
            scheduler (APScheduler): _description_
            app (_type_): While in other services app is optional, it is required here. python will automatically map the kwargs['app'] to this app
        """
        self.scheduler = scheduler

        notifications_endpoint_url = "/".join(
            [scheduler.app.config["EXT_URL_PREFIX"], self.id]
        )
        # remove leading /
        if notifications_endpoint_url.startswith("/"):
            notifications_endpoint_url = notifications_endpoint_url[1:]

        self.notification_manager = NotificationManager(
            scheduler.app.config.get("HOST", "127.0.0.1"),
            scheduler.app.config["PORT"],
            scheduler.app.config["CERT"],
            scheduler.app.config["KEY"],
            enable_websockets=scheduler.app.config[
                "SPECTER_NOTIFICATIONS_WEBSOCKETS_ENABLED"
            ],
            notifications_endpoint_url=notifications_endpoint_url,
        )
        for user in scheduler.app.specter.user_manager.users:
            self.notification_manager.register_user_ui_notifications(user.id)

    # There might be other callbacks you're interested in. Check the callbacks.py in the specter-desktop source.
    # if you are, create a method here which is "callback_" + callback_id

    def callback_flash(self, message: str, category: str = "message"):
        username = (
            current_user if not isinstance(current_user, AnonymousUserMixin) else None
        )
        return self.notification_manager.flash(message, username, category)

    def callback_create_and_show_notification(self, title, **kwargs):
        username = (
            current_user if not isinstance(current_user, AnonymousUserMixin) else None
        )

        return self.notification_manager.create_and_show(title, username, **kwargs)

    def callback_cleanup_on_exit(self, signum=0, frame=0):
        logger.debug(f"callback_cleanup_on_exit called of {self.__class__.__name__}")
        self.notification_manager.quit()

    @classmethod
    def inject_in_basejinja_body_top(cls):
        return render_template("notifications/html_inject_in_basejinja.jinja")
