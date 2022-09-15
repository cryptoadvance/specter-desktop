from flask import flash as flask_flash


def flash(*args, **kwargs):
    """An indirection in order to potentially handle a flash differently
    This function could be placed in util but as it might
    use the service_manager, we place it here for now.
    """
    flask_flash(*args, **kwargs)
