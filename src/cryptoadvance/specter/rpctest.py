import logging
import os, sys, errno
from rpc import *
import requests

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    conf_arr = detect_cli_confs()
    available_conf_arr = []
    if len(conf_arr) > 0:
        print("trying %d different configs" % len(conf_arr))
        for conf in conf_arr:
            cli = BitcoinCLI(**conf)
            try:
                print(cli.getmininginfo(timeout=1))
                print("Yey! Bitcoin-cli found!")
                available_conf_arr.append(cli)
            except requests.exceptions.RequestException:
                print("can't connect")
            except Exception as e:
                print("fail...", e)
    else:
        print("Bitcoin-cli not found :(")
    print("\nDetected %d bitcoin daemons\n" % len(available_conf_arr))
