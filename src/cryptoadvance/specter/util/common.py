import logging
import re
from datetime import datetime
import json
from flask_babel.speaklater import LazyString

logger = logging.getLogger(__name__)


def str2bool(my_str):
    """returns a reasonable boolean from a string so that "False" will result in False"""
    if my_str is None:
        return False
    elif isinstance(my_str, str) and my_str.lower() == "false":
        return False
    elif isinstance(my_str, str) and my_str.lower() == "off":
        return False
    return bool(my_str)


def camelcase2snake_case(name):
    """If you pass DeviceManager it returns device_manager"""
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    name = pattern.sub("_", name).lower()
    return name


def snake_case2camelcase(word):
    return "".join(x.capitalize() or "_" for x in word.split("_"))


def robust_json_dumps(obj):
    def default(o):
        if isinstance(o, datetime):
            return o.timestamp()
        if isinstance(o, set):
            return list(o)
        if isinstance(o, LazyString):
            return str(o)
        logger.warning(
            f"robust_json_dumps could not convert {o} of type {type(o)}.  Converting to string instead."
        )
        return str(o)

    return json.dumps(obj, default=default)
