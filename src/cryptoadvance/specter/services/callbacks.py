""" Here we have some constants getting an id for extension-points/callbacks. As camelcase
    is used, we don't use CAPITAL letters to not loose the meaning of the camelcase.
    
    These constants are expected as parameter to the ServiceManager.callback function
    and it'll throw an exception if the constant does not exist.

    There are some weak naming conventions:
    1. after/before
    2. class or file
    3. method or function
    
"""

"""
    I don't know why we have this one. Doesn't seem to be used anywhere.    
"""
afterServiceManagerInit = "afterServiceManagerInit"

"""
    This one is called, after the init_app method has finished. The "run" method has not 
    been executed yet and so urls can't be called yet.
    So this is the best place for almost all extensions to do their initializing work.
"""
after_serverpy_init_app = "after_serverpy_init_app"

""" Extensions which want to extend the settings dialog
    needs to return something like: return [{"title": "token", "endpoint":"settings_token"}]
    Check the extension-docs for a comprehensive example.
"""
add_settingstabs = "add_settingstabs"

""" Extensions which want to extend the wallet dialog
    needs to return something like: return [{"title": "sometitle", "endpoint":"yourendpoint"}]
    Check the extension-docs for a comprehensive example.
"""
add_wallettabs = "add_wallettabs"

""" Endpoints might define their behaviour via a ViewModel. Those Models are passed here and
    extensions can modify that behaviour via Modifying that model. Currently there is only:
    cryptoadvance.specter.server_enpoints.welcome.welcome_vm.WelcomeVm
"""
adjust_view_model = "adjust_view_model"

"""
    This one is called, whenever a file is persisted. To call external scripts in another
    process, you better use the SPECTER_PERSISTENCE_CALLBACK Env Var or it's asynchronous cousin
    SPECTER_PERSISTENCE_CALLBACK_ASYNC.
"""
specter_persistence_callback = "specter_persistence_callback"

""" 
    Will get called before every request via the Flask's @app.before_request
"""
flask_before_request = "flask_before_request"

""" 
    Will get called right after having access to app.specter
"""
specter_added_to_flask_app = "specter_added_to_flask_app"
