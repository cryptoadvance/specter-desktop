import logging
from flask import Flask
from flask import current_app as app
from threading import Thread

logger = logging.getLogger(__name__)


class FlaskThread(Thread):
    """A FlaskThread passes the applicationcontext to the new thread in order to make stuff working seamlessly in new threadsS
    copied from https://stackoverflow.com/questions/39476889/use-flask-current-app-logger-inside-threading
    In certain situations, that might not appropriate, e.g. if the app-context is not available. So in such cases
    we'll simply fall back to the normal behaviour.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        try:
            self.app = app._get_current_object()
            self.flask_mode = True
        except RuntimeError as e:
            if str(e).startswith("Working outside of application context."):
                self.flask_mode = False
            else:
                raise e

    def run(self):
        if self.flask_mode:
            with self.app.app_context():
                logger.debug(f"starting new FlaskThread: {self._target.__name__}")
                super().run()
        else:
            logger.debug(f"starting new Thread: {self._target.__name__}")
            super().run()
