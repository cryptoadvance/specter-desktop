from logging.config import dictConfig
from .cli import cli

if __name__ == "__main__":
    # central and early configuring of logging see
    # https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })
    cli()
