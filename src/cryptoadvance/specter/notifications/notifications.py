import logging

logger = logging.getLogger(__name__)
import datetime
import hashlib


class NotificationTypes:
    debug = "debug"
    information = "information"
    warning = "warning"
    error = "error"
    exception = "exception"


class Notification:
    "A Notification is a datastructure to store title, body, ..."

    def __init__(self, title, notification_type=None, body=None, **kwargs):
        self.title = title
        self.date = datetime.datetime.now()
        self.deleted = False
        self.first_read = None
        self.body = body
        self.icon = None
        self.timeout = None
        self.type = (
            notification_type if notification_type else NotificationTypes.information
        )
        self.id = None

        if self.type not in {
            NotificationTypes.debug,
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }:
            self.type = NotificationTypes.information

        self._set_id()

    def _set_id(self):
        reduced_dict = self.__dict__().copy()
        del reduced_dict["id"]
        del reduced_dict["deleted"]
        self.id = hashlib.sha256(self.__str__().encode()).hexdigest()

    def __dict__(self):
        return {
            "title": self.title,
            "date": self.date.isoformat(),
            "deleted": self.deleted,
            "first_read": self.first_read,
            "body": self.body,
            "icon": self.icon,
            "timeout": self.timeout,
            "type": self.type,
            "id": self.id,
        }

    def __str__(self):
        return str(self.__dict__())
