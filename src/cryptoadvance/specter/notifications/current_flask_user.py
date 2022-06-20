from flask import current_app as app


def flash(title, **kwargs):
    app.specter.notification_manager.flash(
        title, app.specter.user_manager.get_user().id, **kwargs
    )


def create_and_show(self, title, **kwargs):
    app.specter.notification_manager.create_and_show(
        title, app.specter.user_manager.get_user().id, **kwargs
    )
