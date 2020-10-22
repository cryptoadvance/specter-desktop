from logging.config import dictConfig
from cryptoadvance.specter.cli import server
import sys

if __name__ == "__main__":
    # central and early configuring of logging see
    # https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
                }
            },
            "handlers": {
                "wsgi": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://flask.logging.wsgi_errors_stream",
                    "formatter": "default",
                }
            },
            "root": {"level": "INFO", "handlers": ["wsgi"]},
        }
    )
    if "--daemon" in sys.argv:
        print("Daemon mode is not supported in binaries yet")
        sys.exit(1)
    if "--debug" in sys.argv:
        print("Debug mode is useless in binary mode, don't use it")
        sys.exit(1)
    if "--hwibridge" not in sys.argv:
        sys.argv.append("--hwibridge")
    server()
