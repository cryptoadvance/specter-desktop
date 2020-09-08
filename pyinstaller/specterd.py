from logging.config import dictConfig
from cryptoadvance.specter.cli import server
import sys
import logging

if __name__ == "__main__":
    # central and early configuring of logging see
    # https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    ch.setFormatter(formatter)
    logging.getLogger().addHandler(ch)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger(__name__).info("Logging configured")
        
    if "--daemon" in sys.argv:
        print("Daemon mode is not supported in binaries yet")
        sys.exit(1)
    if "--debug" in sys.argv:
        print("Debug mode is useless in binary mode, don't use it")
        sys.exit(1)
    print("Starting Specter server. It may take a while, please be patient")
    server()
