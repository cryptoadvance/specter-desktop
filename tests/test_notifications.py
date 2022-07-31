import logging
from mock import MagicMock, call, patch
import pytest
from cryptoadvance.specter.specter import Specter, UserManager
from cryptoadvance.specter.notifications.notification_manager import NotificationManager
import datetime

logger = logging.getLogger(__name__)


@pytest.fixture
def specter_with_user(empty_data_folder):
    """This assumes a bitcoin-testnet-node is running on loalhost"""

    specter = Specter(data_folder=empty_data_folder)
    user_manager = UserManager(specter=specter)

    password = "somepassword"
    user_id = "someuser"
    username = "someuser"
    config = {}

    user = user_manager.create_user(
        user_id=user_id, username=username, plaintext_password=password, config=config
    )
    yield specter


# Create NotificationManger   and send a print notification, check that on_show and on_close was called exactly 1 once
#  and check that delete_notification was called only once.
#  check than that the notification database is empty.
def test_sending_print_notification(specter_with_user: Specter, caplog):

    notification_manager = NotificationManager(
        specter_with_user.user_manager,
        host="localhost",
        port="1234",
        ssl_cert=None,
        ssl_key=None,
        enable_websockets=False,
    )

    # do not take the admin user but the "someuser", just to make sure "someuser" can use the  default_ui_notifications
    user = specter_with_user.user_manager.get_user("someuser")
    ui_notifications_of_user = notification_manager._get_ui_notifications_of_user(
        user.username
    )

    # _register_default_ui_notifications should have created 2 ui_notifications accessible for all users
    assert len(ui_notifications_of_user) == 2

    notification = notification_manager.create_notification(
        "testing title",
        user.username,
        target_uis="default",
        date=datetime.datetime(2022, 7, 31, 20, 23, 49, 541516),
    )
    # the notification was stored in notification_manager.notifications
    assert len(notification_manager.notifications) == 1

    # capture if the notification was actually shown
    with caplog.at_level(logging.INFO):
        notification_manager.show(notification)

    # check if any of the INFO messages was the notification
    notification_found = False
    for record in caplog.records:
        if (
            record.message
            == "{'title': 'testing title', 'user_id': 'someuser', 'date': datetime.datetime(2022, 7, 31, 20, 23, 49, 541516), 'last_shown_date': {}, 'was_closed_in_target_uis': set(), 'target_uis': {'logging'}, 'notification_type': 'information', 'body': None, 'data': None, 'image': None, 'icon': None, 'timeout': None, 'id': '66df153241a18b94cc658123edee822fb45528c30af78fc6db5a2e1606830eda'}"
            and record.levelname == "INFO"
        ):
            notification_found = True
    assert notification_found

    # the notification was deleted again
    assert len(notification_manager.notifications) == 0
