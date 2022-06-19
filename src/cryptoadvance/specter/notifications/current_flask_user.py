from flask import current_app as app


def flash(*args, **kwargs):
    app.specter.user_manager.get_user().notification_manager.flash(*args, **kwargs)


def create_and_show(self, *args, **kwargs):
    app.specter.user_manager.get_user().notification_manager.create_and_show(
        *args, **kwargs
    )
