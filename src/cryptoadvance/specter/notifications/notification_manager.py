import logging

from cryptoadvance.specter import notifications

logger = logging.getLogger(__name__)

from .notifications import Notification
from ..notifications import ui_notifications


class NotificationManager:
    """
    This class allows to register ui_notifications (like JSNotifications)

    Notifications can be created and broadcasted with self.create_and_show
        This will forward the notification to all appropriate ui_notifications

        The notifications are also stored in self.notifications and
        deleted again in self.on_close

        If the ui_notification noticed later (async), that the notification
        was not delivered, then the ui_notification call
        create_notification('set_target_ui_availability', user_id, target_uis=["internal_notification"], is_available=False)
        and the ui_notification will deactivate and the notification will be rebroadcasted
    """

    def __init__(self, ui_notifications=None):
        """
        Arguments:
            - ui_notifications:  {user_id: [list of ui_notifications]}
                    The "default" ui_notifications is at position 0
        """
        self.ui_notifications = ui_notifications if ui_notifications else []
        self.notifications = []
        self.register_default_ui_notifications()

    def register_default_ui_notifications(self):
        self.register_ui_notification(ui_notifications.LoggingNotifications())
        self.register_ui_notification(ui_notifications.PrintNotifications())

    def register_user_ui_notifications(self, user_id):
        # setting up the notification system for this user

        webapi_notifications = ui_notifications.WebAPINotifications(user_id)
        js_notifications = ui_notifications.JSNotifications(user_id)
        self.register_ui_notification(webapi_notifications)
        self.register_ui_notification(js_notifications)
        self.register_ui_notification(ui_notifications.FlashNotifications(user_id))
        self.register_ui_notification(ui_notifications.JSConsoleNotifications(user_id))
        js_notifications.on_close = self.on_close
        webapi_notifications.on_close = self.on_close

    def register_ui_notification(self, ui_notification):
        logger.debug(
            f'Registering "{ui_notification.name}" for user "{ui_notification.user_id}" in {self.__class__.__name__}'
        )
        self.ui_notifications.append(ui_notification)

    def find_target_ui(self, target_ui, user_id):
        for ui_notification in self.ui_notifications:
            if (ui_notification.name == target_ui) and (
                ui_notification.user_id == user_id
            ):
                return ui_notification

    def set_target_ui_availability(self, target_ui, user_id, is_available):
        ui_notification = self.find_target_ui(target_ui, user_id)
        if not ui_notification:
            logger.warning(
                f"set_target_ui_availability: target_ui {target_ui} could not be found"
            )
            return
        ui_notification.is_available = is_available
        logger.debug(
            f"Setting {ui_notification.name} of user {ui_notification.user_id} available = {is_available}"
        )

    def get_ui_notifications_of_user(self, user_id):
        "Gives a back a [ui_notifications that belong to the user_id] + [ui_notifications that belong to user_id == None]"
        return [
            ui_notification
            for ui_notification in self.ui_notifications
            if ui_notification.user_id == user_id
        ] + [
            ui_notification
            for ui_notification in self.ui_notifications
            if ui_notification.user_id is None
        ]

    def show(self, notification):
        """
        forwards the notification to ui_notifications, that are in notification['target_uis']

        If a target_ui of notification['target_uis'] is not is_available, then try with the next target_ui
        """
        if notification.target_uis == ["internal_notification"]:
            return

        ui_notification_of_user = self.get_ui_notifications_of_user(
            notification.user_id
        )
        broadcast_on_ui_notification = [
            ui_notification
            for ui_notification in ui_notification_of_user
            if (ui_notification.name in notification.target_uis)
        ]

        for ui_notification in broadcast_on_ui_notification:
            notification_broadcasted = ui_notification.show(notification)
            logger.debug(
                f"show {notification} on {ui_notification} returned {notification_broadcasted}, ui_notification.is_available {ui_notification.is_available}"
            )

            # if not possible, then try show it with a ui_notifications that is NOT already in notification['target_uis']
            if not notification_broadcasted:
                logger.debug(
                    f"Trying with other ui_notifications to broadcast {notification}"
                )
                for other_ui_notification in ui_notification_of_user:
                    # if it is already broadcasted on this other_ui_notification by default anyway, no need to do it twice
                    if other_ui_notification in broadcast_on_ui_notification:
                        continue
                    notification_broadcasted = other_ui_notification.show(notification)
                    logger.debug(f"show {notification} on {ui_notification}")
                    if notification_broadcasted:
                        break

    def set_notification_shown(self, notification_id, target_ui):
        notification = self.find_notification(notification_id)
        if not notification:
            logging.warning(
                f"set_notification_shown: Notification with id {notification_id} not found"
            )
            return
        notification.set_shown(target_ui)

    def treat_internal_message(self, internal_notification):
        """
        Notifications with the title='internal_notification'  are not displayed to the user, but used for things like:
        - handling callbacks  (like on_close or on_show)
        - messaging back that a target ui is unavailable (the notification is then also rebroadcasted)
        """
        if "internal_notification" not in internal_notification.target_uis:
            return internal_notification
        logger.debug(f"treat_internal_message {internal_notification}")

        referenced_notification = self.find_notification(
            internal_notification.data["id"]
        )

        if internal_notification.title == "set_target_ui_availability":
            logger.debug(
                f'{internal_notification.data["target_ui"]} is unavailable, now deactivating this target_ui and rebroadcasting'
            )
            self.set_target_ui_availability(
                internal_notification.data["target_ui"],
                internal_notification.user_id,
                internal_notification.data["is_available"],
            )
            if not internal_notification.data["is_available"]:
                # if it is not available rebroadcast
                if not referenced_notification:
                    return
                logger.debug(f"Rebrodcasting {referenced_notification.id}")
                self.show(referenced_notification)

        if internal_notification.title == "on_show":
            self.set_notification_shown(
                referenced_notification.id,
                internal_notification.data["target_ui"],
            )

        if internal_notification.title == "on_close":
            if not referenced_notification:
                return

            for ui_notification in self.ui_notifications:
                # perhaps the target_ui was not available and it was displayed in another ui_notification. However still call the on_close of the original target_ui
                if ui_notification.name == internal_notification.data["target_ui"]:
                    ui_notification.on_close(
                        referenced_notification.id,
                        internal_notification.data["target_ui"],
                    )

    def get_default_target_ui_name(self):
        return self.ui_notifications[0].name if self.ui_notifications else None

    def get_all_target_ui_names(self):
        return {ui_notification.name for ui_notification in self.ui_notifications}

    def create_notification(self, title, user_id, **kwargs):
        """
        Creates a notification (which adds it to self.notifications) and also broadcasts it to ui_notifications.
        kwargs are the optional arguments of Notification
        """
        logger.debug(
            f"Starting to ceated notification with title, **kwargs   {title, kwargs}"
        )

        notification = Notification(
            title,
            self.get_default_target_ui_name(),
            self.get_all_target_ui_names(),
            user_id,
            **kwargs,
        )
        logger.debug(f"Middle of creating notification   {notification}")

        # treat an internal (notification) message
        if "internal_notification" in notification.target_uis:
            # in case       treat_internal_message returns a notification, then proceed with that
            return self.treat_internal_message(notification)

        self.notifications.append(notification)
        logger.debug(f"Created notification {notification}")
        return notification

    def flash(self, message: str, user_id, category: str = "message"):
        self.create_and_show(
            message, user_id, notification_type=category, target_uis={"flash"}
        )

    def create_and_show(self, title, user_id, **kwargs):
        """
        Creates a notification (which adds it to self.notifications) and also broadcasts it to ui_notifications.
        kwargs are the optional arguments of Notification
        """
        notification = self.create_notification(title, user_id, **kwargs)
        if notification:
            self.show(notification)

    def find_notification(self, notification_id):
        for notification in self.notifications:
            if notification.id == notification_id:
                return notification

    def delete_notification(self, notification):
        del self.notifications[self.notifications.index(notification)]
        logger.debug(f"Deleted {notification}")

    def on_close(self, notification_id, target_ui):
        "Deletes the notification.   target_ui is currently not used, but could be in the future"
        notification = self.find_notification(notification_id)
        if not notification:
            logging.debug(f"on_close: Notification with id {notification_id} not found")
            return

        self.delete_notification(notification)
