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


class Notification(dict):
    """
    A Notification is a datastructure to store title, body, ...
    The field names should be ideally identical to https://notifications.spec.whatwg.org/#api
    Additional fields, like id, can be added
    """

    def __init__(
        self,
        title,
        default_target_ui,
        all_target_uis,
        notification_type=None,
        body=None,
        target_uis="default",
        **kwargs
    ):
        self["title"] = str(title)
        self["date"] = datetime.datetime.now()
        self["first_shown"] = None
        self["image"] = None
        self["icon"] = None
        self["body"] = body
        self["timeout"] = None  # [ms]

        if not target_uis:
            target_uis = "default"
        self["target_uis"] = (
            {target_uis} if isinstance(target_uis, str) else set(target_uis)
        )

        # clean up invalid NotificationTypes
        self["type"] = (
            notification_type if notification_type else NotificationTypes.information
        )
        if self["type"] not in {
            NotificationTypes.debug,
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }:
            self["type"] = NotificationTypes.information

        # take over all remeining kwargs
        for key, value in kwargs.items():
            self[key] = value

        self.cleanup_target_uis(default_target_ui, all_target_uis)

        # set id (dependent on all other properties, so must eb set last)
        self["id"] = None
        self._set_id()

    def _set_id(self):
        reduced_dict = self.copy()
        del reduced_dict["id"]
        self["id"] = hashlib.sha256(str(self).encode()).hexdigest()

    def cleanup_target_uis(self, default_target_ui, all_target_uis):
        # clean up the notification['target_uis']
        if "target_uis" not in self:
            self["target_uis"] = set()

        if "internal_notification" in self["target_uis"]:
            # no cleanup for internal_notification
            return

        if "all" in self["target_uis"]:
            self["target_uis"] = all_target_uis

        # replace the "default" target_ui with the 0.th  ui_notifications
        if "default" in self["target_uis"]:
            self["target_uis"].remove("default")
            if default_target_ui:
                self["target_uis"].add(default_target_ui)

    def to_js_notification(self):
        "datastructure is changes such that a Notification(js_notification) can be called https://notifications.spec.whatwg.org/#api for paramters"
        js_notification = {
            "title": self["title"],
            "id": self["id"],
            "type": self["type"],
            "timeout": self["timeout"],
            "options": {},
        }

        for key, value in self.items():
            if key in js_notification:
                continue
            if value is None:
                continue
            js_notification["options"][key] = value

        return js_notification
