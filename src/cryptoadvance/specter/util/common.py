import logging
import re
from datetime import datetime
import json
from flask_babel.speaklater import LazyString
from typing import Union

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


def format_btc_amount_as_sats(value: Union[float, str]) -> str:
    return "{:,.0f}".format(round(float(value) * 1e8))


def format_btc_amount(
    value: Union[float, str],
    maximum_digits_to_strip=7,
    minimum_digits_to_strip=6,
    enable_digit_formatting=True,
) -> str:
    value = round(float(value), 8)
    formatted_amount = "{:,.8f}".format(value)

    count_digits_that_can_be_stripped = 0
    for i in reversed(range(len(formatted_amount))):
        if formatted_amount[i] == "0":
            count_digits_that_can_be_stripped += 1
            continue
        break

    array = list(formatted_amount)
    if count_digits_that_can_be_stripped >= minimum_digits_to_strip:
        for i in reversed(range(len(array))):
            if array[i] == "0" and len(array) - i <= maximum_digits_to_strip:
                array[
                    i
                ] = f'<span class="unselectable transparent-text">{array[i]}</span>'
                continue
            # the following if branch is only relevant if last_digits_to_strip == 8, i.e. all digits can be stripped
            elif formatted_amount[i] == ".":
                array[
                    i
                ] = f'<span class="unselectable transparent-text">{array[i]}</span>'
            break

    if enable_digit_formatting:
        array[-6] = f'<span class="thousand_digits_in_btcamount_formatted">{array[-6]}'
        array[-4] = f"{array[-4]}</span>"
        array[-3] = f'<span class="last_digits_in_btcamount_formatted">{array[-3]}'
        array[-1] = f"{array[-1]}</span>"

    return "".join(array)


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
