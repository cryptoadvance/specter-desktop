import logging
from flask import current_app as app

logger = logging.getLogger(__name__)


def flash(message: str, category: str = "message"):
    if not app or not app.specter or not app.specter.user_manager.get_user():
        logger.warning(
            f"app.specter.user_manager.get_user() cannot be accessed. Cannot print the flash notification with title {message} and category {category}"
            "Using print() for the notification instead"
        )
        print(message, category)
        return
    if not app.specter.notification_manager:
        logger.warning(
            f"app.specter.notification_manager not initialized. Cannot print the flash notification with title {message} and category {category}"
            "Using print() for the notification instead"
        )
        print(message, category)
        return

    app.specter.notification_manager.flash(
        message, app.specter.user_manager.get_user().id, category
    )


def create_and_show(title, **kwargs):
    if not app or not app.specter or not app.specter.user_manager.get_user():
        logger.warning(
            f"app.specter.user_manager.get_user() cannot be accessed. Cannot print the flash notification with title {title} and kwargs {kwargs}"
            "Using print() for the notification instead"
        )
        print(title, kwargs)
        return
    if not app.specter.notification_manager:
        logger.warning(
            f"app.specter.notification_manager not initialized. Cannot print the flash notification with title {title} and category {kwargs}"
            "Using print() for the notification instead"
        )
        print(title, kwargs)
        return

    app.specter.notification_manager.create_and_show(
        title, app.specter.user_manager.get_user().id, **kwargs
    )
