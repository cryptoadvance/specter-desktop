import os, sys, errno
from rpc import *
import requests

def get_default_datadir():
    datadir = None
    if sys.platform == 'darwin':
        datadir = os.path.join(os.environ['HOME'], "Library/Application Support/Bitcoin/")
    elif sys.platform == 'win32':
        datadir = os.path.join(os.environ['HOME'], "Bitcoin")
    else:
        datadir = os.path.join(os.environ['HOME'], ".bitcoin")
    return datadir

def get_rpcconfig():
    path = get_default_datadir()
    config = {
        "bitcoin.conf": {},
        "cookies": [],
    }
    if not os.path.isdir(path): # we don't know where to search for files
        return config
    # load content from bitcoin.conf
    bitcoin_conf_file = os.path.join(path, "bitcoin.conf")
    if os.path.exists(bitcoin_conf_file):
        try:
            with open(bitcoin_conf_file, 'r') as f:
                for line in f.readlines():
                    line = line.split("#")[0]
                    if '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    config["bitcoin.conf"][k.strip()] = v.strip()
        except:
            print("Can't open %s file" % bitcoin_conf_file)
    folders = {
        "main": "", 
        "test": "testnet3",
        "regtest": "regtest",
        "signet": "signet",
    }
    for chain in folders:
        fname = os.path.join(path, folders[chain], ".cookie")
        if os.path.exists(fname):
            try:
                with open(fname, 'r') as f:
                    content = f.read()
                    user, passwd = content.split(":")
                    obj = {
                        "user": user,
                        "passwd": passwd,
                        "port": RPC_PORTS[chain]
                    }
                    config["cookies"].append(obj)
            except:
                print("Can't open %s file" % fname)
    return config

def get_configs(config):
    confs = []
    default = {}
    if "rpcuser" in config["bitcoin.conf"]:
        default["user"] = config["bitcoin.conf"]["rpcuser"]
    if "rpcpassword" in config["bitcoin.conf"]:
        default["passwd"] = config["bitcoin.conf"]["rpcpassword"]
    if "rpchost" in config["bitcoin.conf"]:
        default["host"] = config["bitcoin.conf"]["rpchost"]
    if "rpcport" in config["bitcoin.conf"]:
        default["port"] = int(config["bitcoin.conf"]["rpcport"])
    if "user" in default and "passwd" in default:
        if "port" in default: # only one bitcoin-cli makes sense in this case
            confs.append(default)
            return confs
        else:
            for network in RPC_PORTS:
                o = {"port": RPC_PORTS[network]}
                o.update(default)
                confs.append(o)
            return confs
    # try cookies now
    for cookie in config["cookies"]:
        o = {}
        o.update(default)
        print(cookie)
        o.update(cookie)
        confs.append(o)
    return confs

def detect_cli(config=None):
    if config is None:
        config = get_rpcconfig()
    rpcconfs = get_configs(config)
    cli_arr = []
    for conf in rpcconfs:
        print(conf)
        cli_arr.append(BitcoinCLI(**conf))
    return cli_arr

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
