import logging

logger = logging.getLogger(__name__)
import datetime


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
        self.type = (
            notification_type if notification_type else NotificationTypes.information
        )
        self.id = None

        self._set_id()

    def _set_id(self):
        dict_without_id = self.__dict__()
        del dict_without_id["id"]
        self.id = hash(self.__str__())

    def __dict__(self):
        return {
            "title": self.title,
            "date": self.date,
            "deleted": self.deleted,
            "first_read": self.first_read,
            "body": self.body,
            "icon": self.icon,
            "type": self.type,
            "id": self.id,
        }

    def __str__(self):
        return str(self.__dict__())
