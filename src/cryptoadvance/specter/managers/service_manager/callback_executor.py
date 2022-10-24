from ...services import callbacks, ExtensionException


class CallbackExecutor:
    """encapsulating the complexities of the extension callbacks"""

    def __init__(self, services):
        self.services = services

    def execute_ext_callbacks(self, callback_id, *args, **kwargs):
        """will execute the callback function for each extension which has defined that method
        the callback_id needs to be passed and specify why the callback has been called.
        It needs to be one of the constants defined in cryptoadvance.specter.services.callbacks
        """
        if callback_id not in dir(callbacks):
            raise Exception(f"Non existing callback_id: {callback_id}")
        # No debug statement here possible as this is called for every request and would flood the logs
        # logger.debug(f"Executing callback {callback_id}")
        return_values = {}
        for ext in self.services.values():
            if hasattr(ext, f"callback_{callback_id}"):
                return_values[ext.id] = getattr(ext, f"callback_{callback_id}")(
                    *args, **kwargs
                )
            elif hasattr(ext, "callback"):
                return_values[ext.id] = ext.callback(callback_id, *args, **kwargs)
        # Filtering out all None return values
        return_values = {k: v for k, v in return_values.items() if v is not None}
        # logger.debug(f"return_values for callback {callback_id} {return_values}")
        return return_values
