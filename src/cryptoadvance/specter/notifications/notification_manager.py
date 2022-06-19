import logging, datetime

logger = logging.getLogger(__name__)

from .notifications import Notification


class NotificationManager:
    "Stores and distributes notifications to 1 or more ui_notifications"

    def __init__(self, ui_notifications):
        """
        Arguments:
            - ui_notifications: A list of ui_notifications with the "default" one in position 0 and if (not available), the next ui_notification
        """
        self.ui_notifications = ui_notifications
        self.notifications = []

    def deactivate_target_ui(self, target_ui):
        for ui_notification in self.ui_notifications:
            if ui_notification.name == target_ui:
                ui_notification.is_available = False
                logger.debug(f"deactivating {ui_notification.name }")

    def show(self, notification):
        """
        forwards the notification to ui_notifications, that are in notification['target_uis']

        If a target_ui of notification['target_uis'] is not is_available, then try with the next target_ui
        """
        if notification["target_uis"] == ["internal_notification"]:
            return

        logger.debug(f"show {notification}")

        for ui_notification in self.ui_notifications:
            if ui_notification.name in notification["target_uis"]:

                notification_shown = ui_notification.show(notification)

                # if not possible, then try show it with a ui_notifications that is NOT already in notification['target_uis']
                if not notification_shown:
                    logger.debug(
                        f"Trying with other ui_notifications to broadcast {notification}"
                    )
                    for ui_notification in self.ui_notifications:
                        if ui_notification.name not in notification["target_uis"]:
                            notification_shown = ui_notification.show(notification)
                            if notification_shown:
                                break

    def set_notification_read_now(self, notification_id):
        notification = self.find_notification(notification_id)
        notification["first_shown"] = datetime.datetime.now()
        logger.debug(f"set_notification_read_now {notification }")

    def treat_internal_message(self, internal_notification):
        "treat an internal_notification"
        if "internal_notification" not in internal_notification["target_uis"]:
            return internal_notification
        logger.debug(f"treat_internal_message {internal_notification}")

        referenced_notification = self.find_notification(
            internal_notification["body"]["id"]
        )

        if internal_notification["title"] == "webapi_notification_unavailable":
            # deactivate target_ui and rebroadcast
            logger.debug(
                "webapi_notification is unavailable, now deactivating this target_ui and rebroadcasting"
            )
            self.deactivate_target_ui("WebAPI")
            if not referenced_notification:
                return
            self.show(referenced_notification)

        if internal_notification["title"] == "notification_shown":
            self.set_notification_read_now(referenced_notification["id"])

        if internal_notification["title"] == "callback_notification_close":
            if not referenced_notification:
                return

            # append ui_notifications to a list, that belong to referenced_notification['target_uis']
            matching_ui_notifications = []
            for ui_notification in self.ui_notifications:
                if ui_notification.name in referenced_notification["target_uis"]:
                    matching_ui_notifications.append(ui_notification)

            # call all callback_notification_close functions of matching_ui_notifications
            for ui_notification in matching_ui_notifications:
                if (
                    "callback_notification_close" in dir(ui_notification)
                    and ui_notification.callback_notification_close
                ):
                    ui_notification.callback_notification_close(
                        referenced_notification["id"]
                    )

    def get_default_target_ui_name(self):
        return self.ui_notifications[0].name if self.ui_notifications else None

    def get_all_target_ui_names(self):
        return {ui_notification.name for ui_notification in self.ui_notifications}

    def create_notification(self, title, **kwargs):
        """
        The arguments are identical to Notification(....), e.g.
            - title
            - None
            - body=None
            - target_uis='default'
        """
        logger.debug(
            f"Starting to ceated notification with title, **kwargs   {title, kwargs}"
        )

        notification = Notification(
            title,
            self.get_default_target_ui_name(),
            self.get_all_target_ui_names(),
            **kwargs,
        )
        logger.debug(f"Middle of creating notification   {notification}")

        # treat an internal (notification) message
        if "internal_notification" in notification["target_uis"]:
            # in case       treat_internal_message returns a notification, then proceed with that
            return self.treat_internal_message(notification)

        self.notifications.append(notification)
        logger.debug(f"Created notification {notification}")
        return notification

    def flash(self, message: str, category: str = "message"):
        self.create_and_show(message, notification_type=category, target_uis={"flash"})

    def create_and_show(self, title, **kwargs):
        """
        The arguments are identical to Notification(....), e.g.
            - title
            - None
            - body=None
            - target_uis='default'
        """
        notification = self.create_notification(title, **kwargs)
        if notification:
            self.show(notification)

    def find_notification(self, notification_id):
        for notification in self.notifications:
            if notification["id"] == notification_id:
                return notification

    def callback_notification_close(self, notification_id):
        notification = self.find_notification(notification_id)
        if not notification:
            return

        del self.notifications[self.notifications.index(notification)]
        logger.debug(f"Deleted {notification}")
