import logging

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
                ui_notification.is_active = False

    def show(self, notification):
        """
        forwards the notification to ui_notifications, that are in notification.target_uis

        If a target_ui of notification.target_uis is not is_available, then try with the next target_ui
        """

        if notification.target_uis == ["internal_notification"]:
            return

        for ui_notification in self.ui_notifications:
            if ui_notification.name in notification.target_uis:

                notification_shown = ui_notification.show(notification)

                # if not possible, then try show it with a ui_notifications that is NOT already in notification.target_uis
                if not notification_shown:
                    logger.debug(
                        f"Trying with other ui_notifications to broadcast {notification}"
                    )
                    for ui_notification in self.ui_notifications:
                        if ui_notification.name not in notification.target_uis:
                            notification_shown = ui_notification.show(notification)
                            if notification_shown:
                                break

    def treat_internal_message(self, notification):
        "treat an internal (notification) message"
        if notification.title == "webapi_notification_unavailable":
            logger.info(
                "webapi_notification is unavailable, now deactivating this target_ui"
            )
            self.deactivate_target_ui("WebAPI")
        if notification.title == "callback_notification_close":
            notification_id = notification.body

            notification = [
                notification
                for notification in self.notifications
                if notification.id == notification_id
            ]
            if not notification:
                return
            else:
                notification = notification[0]

            # append ui_notifications to a list, that belong to notification.target_uis
            matching_ui_notifications = []
            for ui_notification in self.ui_notifications:
                if ui_notification.name in notification.target_uis:
                    matching_ui_notifications.append(ui_notification)

            # call all callback_notification_close functions of matching_ui_notifications
            for ui_notification in matching_ui_notifications:
                if ui_notification.callback_notification_close:
                    ui_notification.callback_notification_close(notification_id)

    def create_notification(self, *args, **kwargs):
        """
        The arguments are identical to Notification(....), e.g.
            - title
            - notification_type=None
            - body=None
            - target_uis='default'
        """
        # clean up the kwargs['target_uis']
        if "target_uis" in kwargs:
            # convert to set
            kwargs["target_uis"] = (
                {kwargs["target_uis"]}
                if isinstance(kwargs["target_uis"], str)
                else kwargs["target_uis"]
            )
            if "all" in kwargs["target_uis"]:
                kwargs["target_uis"] = {
                    ui_notification.name for ui_notification in self.ui_notifications
                }
            # replace the "default" target_ui with the 0.th  ui_notifications
            if "default" in kwargs["target_uis"]:
                idx = kwargs["target_uis"].index("default")
                kwargs["target_uis"][idx] = (
                    {self.ui_notifications[0].name} if self.ui_notifications else {}
                )

        notification = Notification(*args, **kwargs)

        # treat an internal (notification) message
        if notification.target_uis == ["internal_notification"]:
            # in case       treat_internal_message returns a notification, then proceed with that
            return self.treat_internal_message(notification)

        self.notifications.append(notification)
        return notification

    def create_and_show(self, *args, **kwargs):
        """
        The arguments are identical to Notification(....), e.g.
            - title
            - notification_type=None
            - body=None
            - target_uis='default'
        """
        notification = self.create_notification(*args, **kwargs)
        if notification:
            self.show(notification)

    def find_notification(self, notification_id):
        for notification in self.notifications:
            if notification.id == notification_id:
                return notification

    def callback_notification_close(self, notification_id):
        notification = self.find_notification(notification_id)
        if not notification:
            return
        notification.deleted = True
        print(f"Closed {notification}")
