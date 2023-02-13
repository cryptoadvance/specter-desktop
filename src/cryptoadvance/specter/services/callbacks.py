""" Here we have classes extension-points/callbacks.
    
    These constants are expected as parameter to the ExtensionManager.callback function
    and it'll throw an exception if the constant does not exist.
    Callbacks have a return_style which determines how the return values get collected:
    * "collect" will return a dict where the key is the id of the extension and the value is
        the returnvalue of that extension
    * "middleware" will expect that the extension is returning something which will in turn
        get a parameter to the next extension`s call. The last extension's returnvalue will
        then become the returnvalue of the callback.
    There are some weak naming conventions:
    1. after/before
    2. class or file
    3. method or function
    callbacks 
    
"""


class Callback:
    return_style = "collect"


class afterExtensionManagerInit(Callback):
    """
    I don't know why we have this one. Doesn't seem to be used anywhere.
    """

    id = "afterExtensionManagerInit"


class after_serverpy_init_app(Callback):
    """
    This one is called, after the init_app method has finished. The "run" method has not
    been executed yet and so urls can't be called yet.
    So this is the best place for almost all extensions to do their initializing work.
    """

    id = "after_serverpy_init_app"


class add_settingstabs(Callback):
    """Extensions which want to extend the settings dialog
    needs to return something like: return [{"title": "token", "endpoint":"settings_token"}]
    Check the extension-docs for a comprehensive example.
    """

    id = "add_settingstabs"


class add_wallettabs(Callback):
    """Extensions which want to extend the wallet dialog
    needs to return something like: return [{"title": "sometitle", "endpoint":"yourendpoint"}]
    Check the extension-docs for a comprehensive example.
    """

    id = "add_wallettabs"


class adjust_view_model(Callback):
    """Endpoints might define their behaviour via a ViewModel. Those Models are passed here and
    extensions can modify that behaviour via Modifying that model. Currently there is only:
    cryptoadvance.specter.server_enpoints.welcome.welcome_vm.WelcomeVm
    """

    id = "adjust_view_model"
    return_style = "middleware"


class specter_persistence_callback(Callback):
    """
    This one is called, whenever a file is persisted. To call external scripts in another
    process, you better use the SPECTER_PERSISTENCE_CALLBACK Env Var or it's asynchronous cousin
    SPECTER_PERSISTENCE_CALLBACK_ASYNC.
    """

    id = "specter_persistence_callback"


class flask_before_request(Callback):
    """
    Will get called before every request via the Flask's @app.before_request
    """

    id = "flask_before_request"


class specter_added_to_flask_app(Callback):
    """
    Will get called right after having access to app.specter
    """

    id = "specter_added_to_flask_app"


class flash(Callback):
    """Will get called if anyone is calling server_endpoionts.flash"""

    id = "flash"


class cleanup_on_exit(Callback):
    """
    Callback that is called last in specter.cleanup_on_exit()
    """

    id = "cleanup_on_exit"


# ToDo: Think about this callback as it's specific to the notification-extension
# We have now the possibility that callbacks are added by extensions but on the other hand
# Core code should not execute code which got specified in extensions.
# Maybe we could weaken that principle, though.
class create_and_show_notification(Callback):
    """
    Callback that is not used yet, but could be implmented in server_endpoints just as flash
    """

    id = "create_and_show_notification"
