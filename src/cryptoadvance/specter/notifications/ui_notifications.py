import logging

logger = logging.getLogger(__name__)

from .notifications import NotificationTypes
from flask import flash


class BaseUINotifications:
    "A base class defining functions that every user faced UI Notification display system should have"

    def __init__(self, on_close=None, on_show=None):
        self.compatible_notification_types = {
            NotificationTypes.debug,
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.name = "base"
        self.is_available = True
        self.user_id = None
        self.callable_from_any_thread = True
        self.on_close = on_close
        self.on_show = on_show

    def show(self, notification):
        pass

    def __repr__(self):
        return str({"class name": self.__class__.__name__, "attributes": self.__dict__})


class PrintNotifications(BaseUINotifications):
    """
    Notifications are shown in print()

    Callback functions are:
    - on_close(notification_id, target_ui), should be assigned to delete the message   (called immediately after showing)
    - on_show(notification_id, target_ui)   (called immediately after showing)
    """

    def __init__(self, on_close=None, on_show=None):
        super().__init__(on_close=on_close, on_show=on_show)
        self.name = "print"

    def show(self, notification):
        if (
            not self.is_available
            or notification.notification_type not in self.compatible_notification_types
        ):
            return
        print(notification)

        notification.set_shown(self.name)
        if self.on_show:
            self.on_show(notification.id, self.name)
        notification.set_closed(self.name)
        if self.on_close:
            self.on_close(notification.id, self.name)
        return True  # successfully broadcasted


class LoggingNotifications(BaseUINotifications):
    """
    Notifications are shown in logger.info()

    Callback functions are:
    - on_close(notification_id, target_ui), should be assigned to delete the message   (called immediately after showing)
    - on_show(notification_id, target_ui)   (called immediately after showing)
    """

    def __init__(self, on_close=None, on_show=None):
        super().__init__(on_close=on_close, on_show=on_show)
        self.name = "logging"

    def show(self, notification):
        if (
            not self.is_available
            or notification.notification_type not in self.compatible_notification_types
        ):
            return
        logger.info(
            str(notification),
            exc_info=notification.notification_type
            in {NotificationTypes.error, NotificationTypes.exception},
        )
        notification.set_shown(self.name)
        if self.on_show:
            self.on_show(notification.id, self.name)
        notification.set_closed(self.name)
        if self.on_close:
            self.on_close(notification.id, self.name)
        return True  # successfully broadcasted


class FlashNotifications(BaseUINotifications):
    """
    Flask flash notifications.  They only appears after render_template is called.

    Callback functions are:
    - on_close(notification_id, target_ui), should be assigned to delete the message   (called immediately after showing)
    - on_show(notification_id, target_ui)   (called immediately after showing)
    """

    def __init__(self, user_id, on_close=None, on_show=None):
        super().__init__(on_close=on_close, on_show=on_show)
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.name = "flash"
        self.user_id = user_id

        #  Flash notifications will not be used as a fallback UINotification,
        #       because they seem to be incompatible with the multi-threading approach in websockets_server_client
        #       Hence, here we set:
        self.callable_from_any_thread = False

    def show(self, notification):
        if (
            not self.is_available
            or notification.notification_type not in self.compatible_notification_types
        ):
            return
        flash(
            f"{notification.title}\n{notification.body if notification.body else ''}",
            notification.notification_type,
        )
        notification.set_shown(self.name)
        if self.on_show:
            self.on_show(notification.id, self.name)
        notification.set_closed(self.name)
        if self.on_close:
            self.on_close(notification.id, self.name)
        return True  # successfully broadcasted


class JSConsoleNotifications(BaseUINotifications):
    """
    Shows the notifications in the javascript console. The logic is mostly in notifications.js

    Callback functions are:
    - on_close(notification_id, target_ui), should be assigned to delete the message
    - on_show(notification_id, target_ui)
    """

    def __init__(self, user_id, websockets_client, on_close=None, on_show=None):
        super().__init__(on_close=on_close, on_show=on_show)
        if not websockets_client:
            raise Exception("websockets_client not set")
        self.name = "js_console"
        self.user_id = user_id
        self.websockets_client = websockets_client

    def show(self, notification):
        if (
            not self.is_available
            or notification.notification_type not in self.compatible_notification_types
        ):
            return

        # convert to json object and set the target_ui as only self.name.
        # The Notification manager handles sending to other target_uis
        js_notification = notification.to_js_notification()
        js_notification["options"]["target_uis"] = [self.name]
        if not self.websockets_client:
            logger.info(
                f"{self.__class__.__name__}.websockets_client of user {self.user_id} returned {self.websockets_client} --> Setting is_available = false. "
            )
            self.is_available = False
            return False
        self.websockets_client.send(js_notification)
        return True  # successfully broadcasted


class JSNotifications(JSConsoleNotifications):
    """
    A javascript message box. The logic is mostly in notifications.js

    Callback functions are:
    - on_close(notification_id, target_ui), should be assigned to delete the message
    - on_show(notification_id, target_ui)
    """

    def __init__(self, user_id, websockets_client, on_close=None, on_show=None):
        super().__init__(user_id, websockets_client, on_close=on_close, on_show=on_show)
        self.compatible_notification_types = {
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }
        self.name = "js_message_box"


class WebAPINotifications(JSNotifications):
    """
    Calls push-notification-style notification, that is realized via Notification_API
    https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API


    Callback functions are:
    - on_close(notification_id, target_ui), should be assigned to delete the message
    - on_show(notification_id, target_ui)
    """

    def __init__(self, user_id, websockets_client, on_close=None, on_show=None):
        super().__init__(user_id, websockets_client, on_close=on_close, on_show=on_show)
        self.name = "webapi"  # see https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
