import logging

logger = logging.getLogger(__name__)

from .notifications import Notification


class NotificationManager:
    "Stores and distributes notifications to 1 or more ui_notifications"

    def __init__(self, ui_notifications):
        self.ui_notifications = ui_notifications
        self.notifications = []

    def show(self, notification):
        "stores and forwards the notification to all self.ui_notifications"
        self.notifications.append(notification)
        for ui_notification in self.ui_notifications:
            ui_notification.show(notification)

    def create_and_show(self, *args, **kwargs):
        notification = Notification(*args, **kwargs)
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
