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


def replace_substring(text, start_position, replace_length, new_str):
    return text[:start_position] + new_str + text[start_position + replace_length :]


def satamount_formatted(value):
    return "{:,.0f}".format(round(float(value) * 1e8))


def btcamount_formatted(
    value,
    maximum_digits_to_strip=7,
    minimum_digits_to_strip=6,
    enable_digit_spaces_for_counting=True,
):
    value = round(float(value), 8)
    formatted_amount = "{:,.8f}".format(value)

    count_digits_that_can_be_stripped = 0
    for i in reversed(range(len(formatted_amount))):
        if formatted_amount[i] == "0":
            count_digits_that_can_be_stripped += 1
            continue
        break

    if count_digits_that_can_be_stripped >= minimum_digits_to_strip:
        for i in reversed(range(len(formatted_amount))):
            if (
                formatted_amount[i] == "0"
                and len(formatted_amount) - i <= maximum_digits_to_strip
            ):
                # replace with https://unicode-table.com/en/2007/
                formatted_amount = replace_substring(formatted_amount, i, 1, "\u2007")
                continue
            # the following if branch is only relevant if last_digits_to_strip == 8, i.e. all digits can be stripped
            elif formatted_amount[i] == ".":
                # replace with https://unicode-table.com/en/2008/
                formatted_amount = replace_substring(formatted_amount, i, 1, "\u2008")
            break

    if enable_digit_spaces_for_counting:
        # strip last digits for better readability and replace with invisible characters
        for i in [-3, -7]:
            formatted_amount = replace_substring(formatted_amount, i, 0, "\u2008")

    return formatted_amount


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
