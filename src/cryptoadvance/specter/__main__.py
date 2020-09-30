from logging.config import dictConfig
from .cli import cli
import logging

if __name__ == "__main__":
    # central and early configuring of logging see
    # https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    # However the dictConfig doesn't work, so let's do something similiar programatically
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    ch.setFormatter(formatter)
    logging.getLogger().addHandler(ch)
    # However initially, we'll set the root-logger to INFO:
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger(__name__).info("Logging configured")
    cli()
