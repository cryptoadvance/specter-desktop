from logging.config import dictConfig
from .cli import cli
import logging

if __name__ == "__main__":
    # central and early configuring of logging see
    # https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    # However the dictConfig doesn't work, so let's do something similiar programatically
    ch = logging.StreamHandler()
    # We only have one Handler. The handler is the last resort of not showing a specific
    # message. So in order to even be able that DEBUG-messages get through, we need
    # to have a very liberal handler. Set it to DEBUG:
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    ch.setFormatter(formatter)
    logging.getLogger().addHandler(ch)
    # However initially, we'll set the root-logger to INFO:
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger(__name__).info("Logging configured")
    cli()
