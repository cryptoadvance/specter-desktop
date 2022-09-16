import logging
from flask import current_app as app
from flask_login import current_user, AnonymousUserMixin

logger = logging.getLogger(__name__)


def flash(message: str, category: str = "message"):
    if not app.specter.ext.get("notifications"):
        logger.warning(
            f"'notifications' not initialized. Cannot print the flash notification with title {message} and category {category}"
            "Using print() for the notification instead"
        )
        print(message, category)
        return

    username = (
        current_user if not isinstance(current_user, AnonymousUserMixin) else None
    )
    app.specter.ext.get("notifications").notification_manager.flash(
        message, username, category
    )


def create_and_show(title, **kwargs):
    if not app.specter.ext.get("notifications").notification_manager:
        logger.warning(
            f"app.specter.notification_manager not initialized. Cannot print the flash notification with title {title} and category {kwargs}"
            "Using print() for the notification instead"
        )
        print(title, kwargs)
        return

    username = (
        current_user if not isinstance(current_user, AnonymousUserMixin) else None
    )

    app.specter.ext.get("notifications").notification_manager.create_and_show(
        title, username, **kwargs
    )
