import os, sys, errno
from rpc import *
import requests

if __name__ == '__main__':
    cli_arr = detect_cli()
    available_cli_arr = []
    if len(cli_arr) > 0:
        print("trying %d different configs" % len(cli_arr))
        for cli in cli_arr:
            try:
                print(cli.getmininginfo(timeout=1))
                print("Yey! Bitcoin-cli found!")
                available_cli_arr.append(cli)
            except requests.exceptions.RequestException:
                print("can't connect")
            except Exception as e:
                print("fail...", e)
    else:
        print("Bitcoin-cli not found :(")
    print("\nDetected %d bitcoin daemons\n" % len(available_cli_arr))
