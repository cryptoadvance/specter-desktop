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
        user_id,
        target_uis="default",  # "default" will be replaced by default_target_ui
        notification_type=None,
        body=None,
        data=None,
        image=None,
        icon=None,
        timeout=None,
        date=None,
        verbose_debug=False,
    ):
        self.title = str(title)
        self.user_id = user_id
        self.date = date if date else datetime.datetime.now()
        self.last_shown_date = dict()  # structure {'target_ui' : date}
        self.was_closed_in_target_uis = set()  # example: {'webapi', 'logging'}

        if not target_uis:
            target_uis = "default"
        self.target_uis = (
            {target_uis} if isinstance(target_uis, str) else set(target_uis)
        )
        self.substitute_special_target_uis(default_target_ui, all_target_uis)

        # clean up invalid NotificationTypes
        self.notification_type = (
            notification_type if notification_type else NotificationTypes.information
        )
        if self.notification_type not in {
            NotificationTypes.debug,
            NotificationTypes.information,
            NotificationTypes.warning,
            NotificationTypes.error,
            NotificationTypes.exception,
        }:
            self.notification_type = NotificationTypes.information

        self.body = body
        self.data = data
        self.image = image
        self.icon = icon
        self.timeout = timeout  # [ms]

        self.verbose_debug = verbose_debug
        # set id (dependent on (almost) all other properties, so must be set last)
        self.id = None
        self._set_id()

    def __str__(self):
        # .copy() is essential here, otherwise one actually deletes verbose_debug from the object
        reduced_dict = self.__dict__.copy()
        del reduced_dict["verbose_debug"]
        return str(reduced_dict)

    def _set_id(self):
        # .copy() is essential here, otherwise one actually deletes id, verbose_debug from the object
        reduced_dict = self.__dict__.copy()
        del reduced_dict["id"]
        del reduced_dict["verbose_debug"]
        self.id = hashlib.sha256(str(reduced_dict).encode()).hexdigest()

    def set_shown(self, target_ui, date=None):
        self.last_shown_date[target_ui] = date if date else datetime.datetime.now()
        if self.verbose_debug:
            logger.debug(f"set_notification_shown {self}")

    def set_closed(self, target_ui):
        self.was_closed_in_target_uis.add(target_ui)
        if self.verbose_debug:
            logger.debug(f"set_closed {self}")

    def substitute_special_target_uis(self, default_target_ui, all_target_uis):
        """
        It replaces the valid target_uis:
          - "default" by the  default_target_ui
          - "all" by all_target_uis

        Args:
            default_target_ui (_type_): _description_
            all_target_uis (_type_): _description_
        """
        # clean up the notification['target_uis']
        if "internal_notification" in self.target_uis:
            # no cleanup for internal_notification
            return

        if "all" in self.target_uis:
            target_uis = all_target_uis

        # replace the "default" target_ui with the 0.th  ui_notifications
        if "default" in self.target_uis:
            self.target_uis.remove("default")
            if default_target_ui:
                self.target_uis.add(default_target_ui)

    def to_js_notification(self):
        """
        Returns the following data structure:
            {
                "title": title,
                "id": id,
                "notification_type": notification_type,
                "timeout": timeout,
                "options": {
                    ....
                },
            }

            The "options" dict is contains self.__dict__.items(), unless they are included in the main dict.
            The "options" dict could contain all fields as https://notifications.spec.whatwg.org/#api ,
                however not even for target_uis = 'web_api' are all fields supported

            The following circular call , will preserve only the (optional) arguments supported by Notification.__init__()
                        (python) js_notification = notification.to_js_notification()
                    --> (javascript) createNotification(js_notification['title'], js_notification['options']) --> title, options
                    --> (python) notification = Notification(title, ...,  **options)
        """
        js_notification = {
            "title": self.title,
            "id": self.id,
            "notification_type": self.notification_type,
            "timeout": self.timeout,
            "options": {},
        }

        for key, value in self.__dict__.items():
            if key in js_notification or value is None:
                continue
            js_notification["options"][key] = value

        return js_notification

    def to_text(self):
        s = self.title
        if self.body:
            s += f"\n{self.body}"
        if self.data:
            s += f"\nData: {self.data}"
        return s
