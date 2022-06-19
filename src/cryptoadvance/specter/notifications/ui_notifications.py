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
        self.is_available = True

    def show(self, notification):
        pass


class PrintNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.name = "print"

    def show(self, notification):
        if (
            not self.is_available
            or notification["type"] not in self.compatible_notification_types
        ):
            return
        print(notification)
        return True  # successful shown


class LoggingNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.name = "logging"

    def show(self, notification):
        if (
            not self.is_available
            or notification["type"] not in self.compatible_notification_types
        ):
            return
        logger.info(
            str(notification),
            exc_info=notification["type"]
            in {NotificationTypes.error, NotificationTypes.exception},
        )
        return True  # successful shown


class FlashNotifications(BaseUINotifications):
    "Flask flash only appears after render_template"

    def __init__(self):
        super().__init__()
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.name = "flash"

    def show(self, notification):
        if (
            not self.is_available
            or notification["type"] not in self.compatible_notification_types
        ):
            return
        flash(
            f"{notification['title']}\n{notification['body'] if notification['body'] else ''}",
            notification["type"],
        )
        return True  # successful shown


class JSConsoleNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.js_notification_buffer = []
        self.name = "js_console"

    def read_and_clear_js_notification_buffer(self):
        js_notification_buffer = self.js_notification_buffer
        self.js_notification_buffer = []
        return js_notification_buffer

    def show(self, notification):
        """
        This will not show the notification immediately, but write it into a buffer and then it is later fetched by a javascript endless loop

        It will return if the notification was broadcasted
        """
        if (
            not self.is_available
            or notification["type"] not in self.compatible_notification_types
        ):
            return
        self.js_notification_buffer.append(notification.to_js_notification())
        return True  # successful shown


class JSNotifications(JSConsoleNotifications):
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
