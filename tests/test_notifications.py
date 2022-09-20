import logging
from mock import MagicMock, call, patch
import pytest
from cryptoadvance.specter.specter import Specter, UserManager
from cryptoadvance.specterext.notifications.notification_manager import (
    NotificationManager,
)
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


def test_sending_logging_notification(specter_with_user: Specter, caplog):

    notification_manager = NotificationManager(
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

    # _register_default_ui_notifications should have created 3 ui_notifications accessible for all users
    assert len(ui_notifications_of_user) == 3
    assert ui_notifications_of_user[0].name == "logging"
    assert ui_notifications_of_user[1].name == "print"
    assert ui_notifications_of_user[2].name == "flash"

    notification = notification_manager.create_notification(
        "testing title",
        user.username,
        target_uis="default",
        date=datetime.datetime(2022, 7, 31, 20, 23, 49, 541516),
        body="testing body",
        data={"key": 1},
        image="someurl",
        icon="someurl",
        timeout=3000,
    )
    # the notification was stored in notification_manager.notifications
    assert len(notification_manager.notifications) == 1
    assert notification_manager.notifications[0].id == notification.id

    # check if the Notification was created correctly
    notification_str = """{'title': 'testing title', 'user_id': 'someuser', 'date': datetime.datetime(2022, 7, 31, 20, 23, 49, 541516), 'last_shown_date': {}, 'was_closed_in_target_uis': set(), 'target_uis': {'logging'}, 'notification_type': 'information', 'body': 'testing body', 'data': {'key': 1}, 'image': 'someurl', 'icon': 'someurl', 'timeout': 3000, 'id': 'c8b752e0cb679ee13b44497c4b02b11cfafdd378757666b1f9ee805d4a5e7c5a'}"""
    assert str(notification) == notification_str

    # capture if the notification was actually shown
    with caplog.at_level(logging.INFO):
        notification_manager.show(notification)

    # check if any of the INFO messages was the notification
    notification_found = False
    logger.debug(caplog.records[-1])
    for record in caplog.records:
        if record.message == notification.to_text() and record.levelname == "INFO":
            notification_found = True
    assert notification_found

    # the notification was deleted again
    assert len(notification_manager.notifications) == 0


def mock_flash(*args, **kwargs):
    flash_message = str((args, kwargs))
    print(flash_message)
    logger.warning(flash_message)


# check that register_user_ui_notifications registers the flash message
# check that flash messages would send the correct message to flash
@patch("cryptoadvance.specterext.notifications.ui_notifications.flash", mock_flash)
def test_sending_flash_notification(specter_with_user: Specter, caplog):

    notification_manager = NotificationManager(
        host="localhost",
        port="1234",
        ssl_cert=None,
        ssl_key=None,
        enable_websockets=False,
    )

    # do not take the admin user but the "someuser", just to make sure "someuser" can use the  default_ui_notifications
    user = specter_with_user.user_manager.get_user("someuser")
    notification_manager.register_user_ui_notifications(user.username)

    ui_notifications_of_user = notification_manager._get_ui_notifications_of_user(
        user.username
    )

    # _register_default_ui_notifications should have created 3 ui_notifications accessible for all users
    assert len(ui_notifications_of_user) == 3
    assert ui_notifications_of_user[0].name == "logging"
    assert ui_notifications_of_user[1].name == "print"
    assert ui_notifications_of_user[2].name == "flash"

    notification = notification_manager.create_notification(
        "testing title",
        user.username,
        target_uis="flash",
        date=datetime.datetime(2022, 7, 31, 20, 23, 49, 541516),
        body="testing body",
        data={"key": 1},
        image="someurl",
        icon="someurl",
        timeout=3000,
    )
    # the notification was stored in notification_manager.notifications
    assert len(notification_manager.notifications) == 1
    assert notification_manager.notifications[0].id == notification.id

    # check if the Notification was created correctly
    notification_str = """{'title': 'testing title', 'user_id': 'someuser', 'date': datetime.datetime(2022, 7, 31, 20, 23, 49, 541516), 'last_shown_date': {}, 'was_closed_in_target_uis': set(), 'target_uis': {'flash'}, 'notification_type': 'information', 'body': 'testing body', 'data': {'key': 1}, 'image': 'someurl', 'icon': 'someurl', 'timeout': 3000, 'id': '56daf971f214d75949a8888654f398d8b8efe14ab027afa1b3393835d4d3edd8'}"""
    assert str(notification) == notification_str

    # capture if the notification was actually shown. Set it it warning, to only cature the mock_flash message
    with caplog.at_level(logging.WARNING):
        notification_manager.show(notification)

    # check if any of the INFO messages was the notification
    assert (
        caplog.records[-1].message
        == """(("testing title\\ntesting body\\nData: {\'key\': 1}", \'information\'), {})"""
    )
    assert caplog.records[-1].levelname == "WARNING"

    # the notification was deleted again
    assert len(notification_manager.notifications) == 0
