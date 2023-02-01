from flask import flash as flask_flash
from flask import current_app as app
from ..services import callbacks


def flash(*args, **kwargs):
    """An indirection in order to potentially handle a flash differently
    This function could be placed in util but as it might
    use the service_manager, we place it here for now.
    """

    return_values = app.specter.service_manager.execute_ext_callbacks(
        callbacks.flash, *args, **kwargs
    )

    # if no extension handled the callback
    if not return_values:
        flask_flash(*args, **kwargs)
