import logging
from flask import current_app as app

logger = logging.getLogger(__name__)


def flash(message: str, category: str = "message"):
    if not app or not app.specter or not app.specter.user_manager.get_user():
        logger.warning(
            f"app.specter.user_manager.get_user() cannot be accessed. Cannot print the flash notification with title {title} and kwargs {kwargs}"
        )
        return

    app.specter.notification_manager.flash(
        message, app.specter.user_manager.get_user().id, category
    )


def create_and_show(title, **kwargs):
    if not app or not app.specter or not app.specter.user_manager.get_user():
        logger.warning(
            f"app.specter.user_manager.get_user() cannot be accessed. Cannot print the flash notification with title {title} and kwargs {kwargs}"
        )
        return

    app.specter.notification_manager.create_and_show(
        title, app.specter.user_manager.get_user().id, **kwargs
    )
