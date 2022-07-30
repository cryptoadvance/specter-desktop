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

    user = specter_with_user.user_manager.get_user()
    ui_notifications_of_user = notification_manager._get_ui_notifications_of_user(
        user.username
    )

    assert len(ui_notifications_of_user) == 2
    logger.info(f"There are {len(ui_notifications_of_user)} ui_notifications_of_user")

    with caplog.at_level(logging.INFO):
        notification_manager.create_and_show(
            "testing title",
            user.username,
            target_uis="default",
            date=datetime.datetime(2022, 7, 31, 20, 23, 49, 541516),
        )

    assert (
        caplog.records[-1].message
        == "{'title': 'testing title', 'user_id': 'admin', 'date': datetime.datetime(2022, 7, 31, 20, 23, 49, 541516), 'last_shown_date': {}, 'was_closed_in_target_uis': set(), 'target_uis': {'logging'}, 'notification_type': 'information', 'body': None, 'data': None, 'image': None, 'icon': None, 'timeout': None, 'id': '1d6794c6a077deeb1d766bc4db0e26e3855ab76b0df004803cb5e1d7fa8dbe92'}"
    )
