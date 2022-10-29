import logging
from flask import Flask
from flask import current_app as app
from threading import Thread

logger = logging.getLogger(__name__)


class FlaskThread(Thread):
    """A FlaskThread passes the applicationcontext to the new thread in order to make stuff working seamlessly in new threadsS
    copied from https://stackoverflow.com/questions/39476889/use-flask-current-app-logger-inside-threading"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app._get_current_object()
        self.daemon = True

    def run(self):
        logger.debug(f"New thread started {self._target.__name__}")
        with self.app.app_context():
            super().run()
