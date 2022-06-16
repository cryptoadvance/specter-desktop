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
        self.web_notification_visualization = None

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

    def show(self, notification):
        if notification.type not in self.compatible_notification_types:
            return
        flash(
            f"{notification.title}\n{notification.body if notification.body else ''}",
            notification.type,
        )


class JSNotifications(BaseUINotifications):
    def __init__(self):
        super().__init__()
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.js_notification_buffer = []
        self.callback_notification_close = None
        self.web_notification_visualization = "js_message_box"

    def convert_to_js_notification(self, notification):
        "see https://notifications.spec.whatwg.org/#api for datastructure"
        return {
            "title": notification.title,
            "id": notification.id,
            "options": {
                "body": notification.body if notification.body else "",
            },
        }

    def read_and_clear_js_notification_buffer(self):
        js_notification_buffer = self.js_notification_buffer
        self.js_notification_buffer = []
        return js_notification_buffer

    def show(self, notification):
        "This will not show the notification immediately, but write it into a buffer and then it is later fetched by a javascript endless loop"
        if notification.type not in self.compatible_notification_types:
            return
        self.js_notification_buffer.append(
            self.convert_to_js_notification(notification)
        )


class WebAPINotifications(JSNotifications):
    def __init__(self):
        super().__init__()
        self.web_notification_visualization = "WebAPI"  # see https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
