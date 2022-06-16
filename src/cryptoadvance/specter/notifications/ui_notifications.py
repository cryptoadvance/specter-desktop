import logging

logger = logging.getLogger(__name__)

from .notifications import NotificationTypes
from flask import flash


class BaseUINotifications:
    "A base class defining functions that every user fased UI Notification display system should have"

    def __init__(self):
        self.compatible_notification_types = {
            NotificationTypes.debug,
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }

    def show(self, notification):
        pass


class PrintNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        print(notification)


class LoggingNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        logger.info(str(notification))


class FlaskNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        flash(f"{notification.title}\n{notification.body}", notification.type)
