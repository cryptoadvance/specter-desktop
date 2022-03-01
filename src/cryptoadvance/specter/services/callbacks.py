""" Here we have some constants getting an id for extension-points/callbacks. As camelcase
    is used, we don't use CAPITAL letters to not loose the meaning of the camelcase.
    
    These constants are expected as parameter to the ServiceManager.callback function
    and it'll throw an exception if the constant does not exist.

    There are some weak naming conventions:
    1. after/before
    2. class or file
    3. method or function
    
"""

afterServiceManagerInit = "afterServiceManagerInit"
after_serverpy_init_app = "after_serverpy_init_app"
