import logging
import secrets

logger = logging.getLogger(__name__)

from .notifications import Notification
from ..notifications import ui_notifications
from ..notifications import websockets_server_client


INTERNAL_NOTIFICATION_TITLES = {"set_target_ui_availability", "on_show", "on_close"}


class NotificationManager:
    """
    This class allows to register ui_notifications (like JSNotifications).

    1. Notifications can be created and broadcasted with self.create_and_show
        This will forward the notification to all appropriate ui_notifications
        The notifications are also stored in self.notifications.

        Notifications has optimistic notification delivery, meaning:
        - the ui_notifications (like JSNotifications) immediately returns True, meaning the notification
            was delivered, if the ui_notification is not deactivated or has other reasons to deny delivery immediately.
        - If the ui_notifications (like JSNotifications) then later detects it failed to deliver
            after all, the ui_notification has to send a set_target_ui_availability (data.is_available=False, data.notification_id),
            which deactivates the ui_notification and rebroadcasts the notification on other available ui_notifications
        - This optimistic notification delivery was chosen, mainly because the ui_notifications vary greatly
            preventing a common timeout. Only the ui_notification knows how long and best it should retry displaying the notification.
            The best example is Notification_API, which may not have the permission to display yet, but can ask for permission
            repeatedly. The user has the choice to grant it or to deny it, or to wait.
            The print notification on the other hand will always work.
        - final confirmation that the message was seen by the user in the on_show notification sent by the ui_notification


    2. Internal notifications will not be shown, but
        a) deletes the message again from self.notifications
        b) trigger functions like ui_notifications.on_close

        If the ui_notification noticed later (async), that the notification was not delivered, then the ui_notification call
        create_notification('set_target_ui_availability', user_id, target_uis=["internal_notification"], is_available=False)
        and the ui_notification will deactivate and the notification will be rebroadcasted



    1.  Notifications to UINotifications
                                                                ┌───────────────────────┐
                                        ┌─────────────────────► │  FlashNotifications   │
                                        │                       └───────────────────────┘
              ┌───────────────────────┐ │                       ┌───────────────────────┐
              │  NotificationManager  │ ├─────────────────────► │ JSConsoleNotifications│
              │   .create_and_show    │ │                       │                       │
              └───────────────────────┘ │                       └───────────────────────┘
                                        │                       ┌───────────────────────┐
                                        └──────────────────────►│   JSNotifications     │
                                                                └───────────────────────┘

    2. internal_notification  at the example of on_close

                  ┌───────────────────────┐
                  │                       │  if "internal_notification" in notification.target_uis:
                  │  NotificationManager  │ ──────────────────────────────────────►┐
                  │   .create_and_show    │                                        │
                  └───────────────────────┘                                        ▼
                                                                 ┌────────────────────────────┐
                                                                 │  NotificationManager       │
                                                                 │   ._treat_internal_message │
                                                                 │     e.g. on_close          │
                                                                 └─────────────────┬──────────┘
                                                                                   │ on_close
                                                                                   ▼
                   ┌───────────────────────┐                         ┌───────────────────────┐
                   │   JSNotifications     │ ◄─────────────────────┐ │   NotificationManager │
                   │   .on_close           │                       │ │   ._internal_on_close │
                   └───────────────────────┘                       │ └───────────────────────┘
                   ┌───────────────────────┐                       │
                   │  NotificationManager  │                       │
                   │  ._delete_notification│ ◄─────────────────────┘
                   └───────────────────────┘

    """

    def __init__(
        self,
        host,
        port,
        ssl_cert=None,
        ssl_key=None,
        ui_notifications=None,
        enable_websockets=True,
        notifications_endpoint_url="svc/notifications",
        verbose_debug=False,
    ):
        """
        Arguments:
            - ui_notifications:  {user_id: [list of ui_notifications]}
                    The "default" ui_notifications is at position 0
        """
        self.ui_notifications = ui_notifications if ui_notifications else []
        self.notifications = []
        self._websocket_tokens = {}
        self.ssl_cert, self.ssl_key = ssl_cert, ssl_key
        self._register_default_ui_notifications()

        self.verbose_debug = verbose_debug
        self.websockets_server = None
        self.websockets_client = None
        if enable_websockets:
            self.websockets_server = websockets_server_client.WebsocketServer(self)

            #   '/'.join([notifications_endpoint_url, "websocket"]) should be replaced by url_for('notifications_endpoint.websocket')
            # but this leads to an error
            self.websockets_client = websockets_server_client.WebsocketClient(
                host,
                port,
                "/".join([notifications_endpoint_url, "websocket"]),
                self.ssl_cert,
                self.ssl_key,
            )

            # setting this client as broadcaster, meaning it is allowed to send to all
            # connected websocket connections without restrictions
            self.websockets_server.set_as_broadcaster(self.websockets_client.user_token)
            self.websockets_client.start()

    def get_websocket_token(self, user_id):
        if user_id not in self._websocket_tokens:
            self._websocket_tokens[user_id] = secrets.token_urlsafe(128)

        return self._websocket_tokens[user_id]

    @property
    def websocket_tokens(self):
        return self._websocket_tokens

    def quit(self):
        if self.websockets_client and self.websockets_client.is_connected():
            self.websockets_client.quit_server()
        logger.debug(f"{self.__class__.__name__} quit was called.")

    def _register_default_ui_notifications(self):
        "Registers up the logging and print UINotifications, that can be used by alll users  (user_id=None)"
        self.register_ui_notification(ui_notifications.LoggingNotifications())
        self.register_ui_notification(ui_notifications.PrintNotifications())
        # the flask context handles here the user assignment, such that no user_id should be given here
        self.register_ui_notification(ui_notifications.FlashNotifications())

    def register_user_ui_notifications(self, user_id):
        "Registers up the (default) UINotifications for this user"
        if self.websockets_server:
            self.register_ui_notification(
                ui_notifications.WebAPINotifications(user_id, self.websockets_client)
            )

        if self.websockets_server:
            self.register_ui_notification(
                ui_notifications.JSNotifications(user_id, self.websockets_client)
            )

        if self.websockets_server:
            self.register_ui_notification(
                ui_notifications.JSConsoleNotifications(user_id, self.websockets_client)
            )

    def register_ui_notification(self, ui_notification):
        """
        Appends the ui_notification at the end of the self.ui_notifications.

        It can then be explicitly used via notification.target_uis = {ui_notification.name}
        or is used automatically as a fallback if all previous ui_notifications are not available
        """
        logger.debug(
            f'Registering "{ui_notification.name}" for user "{ui_notification.user_id}" in {self.__class__.__name__}'
        )
        self.ui_notifications.append(ui_notification)

    def _find_target_ui(self, target_ui, user_id):
        "Returns the ui_notification matching (target_ui, user_id)"
        for ui_notification in self.ui_notifications:
            if (ui_notification.name == target_ui) and (
                (ui_notification.user_id == user_id or ui_notification.user_id is None)
            ):
                return ui_notification

    def get_default_target_ui_name(self):
        "Returns the first ui_notifications"
        return self.ui_notifications[0].name if self.ui_notifications else None

    def get_all_target_ui_names(self):
        "Returns the names of all ui_notifications"
        return {ui_notification.name for ui_notification in self.ui_notifications}

    def get_notification_by_id(self, notification_id):
        "Finds and returns the notification with notification_id"
        for notification in self.notifications:
            if notification.id == notification_id:
                return notification

    def _get_ui_notifications_of_user(
        self, user_id, callable_from_any_session_required=False
    ):
        "Gives a back a [ui_notifications that belong to the user_id] + [ui_notifications that belong to user_id == None]"
        user_targeted_ui_notification = (
            [
                ui_notification
                for ui_notification in self.ui_notifications
                if ui_notification.user_id == user_id
                and (
                    ui_notification.callable_from_any_session
                    or not callable_from_any_session_required
                )
            ]
            if user_id
            else []
        )

        public_ui_notification = [
            ui_notification
            for ui_notification in self.ui_notifications
            if ui_notification.user_id is None
            and (
                ui_notification.callable_from_any_session
                or not callable_from_any_session_required
            )
        ]

        return user_targeted_ui_notification + public_ui_notification

    def set_notification_shown(self, notification_id, target_ui):
        "Calls notification.set_shown"
        notification = self.get_notification_by_id(notification_id)
        if not notification:
            logging.warning(
                f"set_notification_shown: Notification with id {notification_id} not found"
            )
            return
        notification.set_shown(target_ui)

    def _delete_notification(self, notification):
        "Deletes the notification from self.notifications"
        if notification not in self.notifications:
            logging.warning(
                f"_delete_notification: notification {notification} was not found in self.notifications"
            )
            return

        del self.notifications[self.notifications.index(notification)]
        if self.verbose_debug:
            logger.debug(f"Deleted {notification}")

    def set_target_ui_availability(self, target_ui, user_id, is_available):
        "Sets ui_notification.is_available"
        ui_notification = self._find_target_ui(target_ui, user_id)
        if not ui_notification:
            logger.warning(
                f"set_target_ui_availability: target_ui {target_ui} could not be found"
            )
            return
        ui_notification.is_available = is_available
        logger.debug(
            f"Setting {ui_notification.name} of user {ui_notification.user_id} available = {is_available}"
        )

    def _internal_set_target_ui_availability(
        self, internal_notification, referenced_notification
    ):
        "Calls self.set_target_ui_availability and rebroadcasts the referenced_notification if necessary"
        logger.debug(
            f'{internal_notification.data["target_ui"]} is unavailable, now deactivating this target_ui and rebroadcasting'
        )
        self.set_target_ui_availability(
            internal_notification.data["target_ui"],
            internal_notification.user_id,
            internal_notification.data["is_available"],
        )
        if not internal_notification.data["is_available"]:
            # if it is not available rebroadcast
            if not referenced_notification and internal_notification.data.get("id"):
                logger.warning(
                    f'Rebrodcasting of {internal_notification.data.get("id")} not possible because referenced_notification={referenced_notification}'
                )
                return
            logger.debug(f"Rebrodcasting {referenced_notification.id}")
            self.show(referenced_notification)

    def _internal_on_show(self, internal_notification, referenced_notification):
        "Calls self.set_notification_shown and ui_notification.on_show"
        if not referenced_notification:
            return

        self.set_notification_shown(
            referenced_notification.id,
            internal_notification.data["target_ui"],
        )
        ui_notification = self._find_target_ui(
            internal_notification.data["target_ui"], referenced_notification.user_id
        )
        # perhaps the target_ui was not available and it was displayed in another ui_notification.
        # However still call on_show of the original target_ui
        if ui_notification.on_show:
            ui_notification.on_show(
                referenced_notification.id,
                internal_notification.data["target_ui"],
            )

    def _notification_can_be_deleted(self, notification, on_close_was_called=False):
        "Checks if the target_ui was set in was_closed_in_target_uis, if the target_ui is available"
        available_target_uis = {
            target_ui
            for target_ui in notification.target_uis
            if self._find_target_ui(target_ui, notification.user_id)
            and self._find_target_ui(target_ui, notification.user_id).is_available
        }

        if not on_close_was_called and not available_target_uis:
            logger.debug(
                f"None of the notification.target_uis {notification.target_uis} are available and on_close was not called yet."
                " Keeping this transaction, such that it can be rebroadcastes later."
            )
            return False

        if self.verbose_debug:
            logger.debug(
                f"Notification {notification.id} of user {notification.user_id} was_closed_in_target_uis = {notification.was_closed_in_target_uis}"
            )
        # it it was closed in all available_target_uis, then go ahead and delete the notification
        return not (available_target_uis - notification.was_closed_in_target_uis)

    def _internal_on_close(self, internal_notification, referenced_notification):
        "calls on_close and deletes the notification afterwards"
        if not referenced_notification:
            return

        ui_notification = self._find_target_ui(
            internal_notification.data["target_ui"], referenced_notification.user_id
        )
        # perhaps the target_ui was not available and it was displayed in another ui_notification.
        # However still call on_close of the original target_ui
        if ui_notification.on_close:
            ui_notification.on_close(
                referenced_notification.id,
                internal_notification.data["target_ui"],
            )

        referenced_notification.set_closed(internal_notification.data["target_ui"])
        if self._notification_can_be_deleted(
            referenced_notification, on_close_was_called=True
        ):
            self._delete_notification(referenced_notification)

    def _treat_internal_message(self, internal_notification):
        """
        Notifications with the title='internal_notification'  are not displayed to the user.
        It allows calling the internal functions for:
        - "on_close"
        - "on_show"
        - "set_target_ui_availability" (if not available, the notification is rebroadcasted)
        """
        if "internal_notification" not in internal_notification.target_uis:
            return internal_notification
        if self.verbose_debug:
            logger.debug(f"_treat_internal_message {internal_notification}")

        referenced_notification = self.get_notification_by_id(
            internal_notification.data.get("id")
        )

        if internal_notification.title in INTERNAL_NOTIFICATION_TITLES:
            method = getattr(self, f"_internal_{internal_notification.title}", None)
            if method:
                method(internal_notification, referenced_notification)
            else:
                logger.warning(
                    f"Could not call the method _internal_{internal_notification.title}"
                )

    def create_notification(self, title, user_id, **kwargs):
        """
        Creates a notification (which adds it to self.notifications) and also broadcasts it to ui_notifications.
        kwargs are the optional arguments of Notification
        """
        if self.verbose_debug:
            logger.debug(
                f"Starting to create notification with title, **kwargs   {title, kwargs}"
            )

        notification = Notification(
            title,
            self.get_default_target_ui_name(),
            self.get_all_target_ui_names(),
            user_id,
            **kwargs,
        )

        # treat an internal (notification) message
        if "internal_notification" in notification.target_uis:
            # in case       _treat_internal_message returns a notification, then proceed with that
            return self._treat_internal_message(notification)

        self.notifications.append(notification)
        if self.verbose_debug:
            logger.debug(f"Created notification {notification}")
        return notification

    def show(self, notification):
        """
        forwards the notification to ui_notifications, that are in notification['target_uis']

        If a target_ui of notification['target_uis'] is not is_available, then try with the next target_ui
        """
        if notification.target_uis == ["internal_notification"]:
            return

        ui_notifications_of_user = self._get_ui_notifications_of_user(
            notification.user_id
        )
        if self.verbose_debug:
            logger.debug(f"ui_notifications_of_user {ui_notifications_of_user}")
        broadcast_on_ui_notifications = [
            ui_notification
            for ui_notification in ui_notifications_of_user
            if (ui_notification.name in notification.target_uis)
        ]

        for ui_notification in broadcast_on_ui_notifications:
            logger.debug(
                f"Showing notification {notification.id} on {ui_notification.name}"
            )

            notification_broadcasted = ui_notification.show(notification)

            # if not possible, then try show it with a ui_notifications that is NOT already in notification['target_uis']
            if not notification_broadcasted:
                if self.verbose_debug:
                    logger.debug(
                        f"Trying with other ui_notifications to broadcast {notification}"
                    )
                # I have to restrict the ui_notifications that are used as a backup to callable_from_any_session_required
                # because it it not possible to call a flash notification from another thread (that  failed doing a webapi notification)
                for backup_ui_notification in self._get_ui_notifications_of_user(
                    notification.user_id, callable_from_any_session_required=True
                ):
                    # if it is already broadcasted on this backup_ui_notification by default anyway, no need to do it twice
                    if backup_ui_notification in broadcast_on_ui_notifications:
                        continue
                    notification_broadcasted = backup_ui_notification.show(notification)
                    if self.verbose_debug:
                        logger.debug(
                            f"Rebroadcasted on {backup_ui_notification.name} of {notification} "
                        )
                    if notification_broadcasted:
                        break
        # for some ui_notifications, the last_shown_date and was_closed_in_target_uis is set immediately.
        # then the message can also be delted immediately
        if self._notification_can_be_deleted(notification):
            self._delete_notification(notification)

    def flash(self, message: str, user_id, category: str = "message"):
        "Creates and shows a flask flash message"

        # translate categories
        if category == "info":
            category = "information"
        if category == "warn":
            category = "warning"

        return self.create_and_show(
            message, user_id, notification_type=category, target_uis={"flash"}
        )

    def create_and_show(self, title, user_id, **kwargs):
        """Creates a notification (which adds it to self.notifications) and also broadcasts it to ui_notifications.

        Args:
            title (str): _description_
            user_id (str): The user.username (or flask.current_user), to whom the notification should be sent
            kwargs: are the optional arguments and will be passed to Notification()

        Returns:
            Notification(): _description_
        """
        notification = self.create_notification(title, user_id, **kwargs)
        if notification:
            self.show(notification)
        return notification
