from logging.config import dictConfig
from .cli import entry_point
import logging

if __name__ == "__main__":
    # central and early configuring of logging see
    # https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    # However the dictConfig doesn't work, so let's do something similiar programatically
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    ch.setFormatter(formatter)
    logging.getLogger().addHandler(ch)
    # However initially, we'll set the root-logger to INFO:
    logging.getLogger("cryptoadvance").setLevel(logging.INFO)
    logging.getLogger("cryptoadvance.specter.util.checker").setLevel(logging.DEBUG)
    entry_point()
