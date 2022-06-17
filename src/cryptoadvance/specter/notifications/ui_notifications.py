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
        self.name = "base"

    def show(self, notification):
        pass


class PrintNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.name = "print"

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        print(notification)


class LoggingNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.name = "logging"

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        logger.info(
            str(notification),
            exc_info=notification.type
            in {NotificationTypes.error, NotificationTypes.exception},
        )


class FlaskNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.name = "flask"

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        flash(
            f"{notification.title}\n{notification.body if notification.body else ''}",
            notification.type,
        )


class JSLoggingNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.js_notification_buffer = []
        self.name = "js_logging"

    def read_and_clear_js_notification_buffer(self):
        js_notification_buffer = self.js_notification_buffer
        self.js_notification_buffer = []
        return js_notification_buffer

    def show(self, notification):
        "This will not show the notification immediately, but write it into a buffer and then it is later fetched by a javascript endless loop"
        if notification.type not in self.compatible_notification_types:
            return
        self.js_notification_buffer.append(notification.to_js_notification())


class JSNotifications(JSLoggingNotifications):
    def __init__(self):
        super().__init__()
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.callback_notification_close = None
        self.name = "js_message_box"


class WebAPINotifications(JSNotifications):
    def __init__(self):
        super().__init__()
        self.name = "WebAPI"  # see https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
