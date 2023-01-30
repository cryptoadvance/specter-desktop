import logging
import re
from datetime import datetime
import json
from flask_babel.speaklater import LazyString
from typing import Union
from distutils.util import strtobool

logger = logging.getLogger(__name__)


def str2bool(my_str):
    """returns a reasonable boolean from a string so that "False" will result in False"""
    if my_str is None:
        return False
    elif isinstance(my_str, bool):
        return my_str
    return bool(strtobool(my_str))


def camelcase2snake_case(name):
    """If you pass DeviceManager it returns device_manager"""
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    name = pattern.sub("_", name).lower()
    return name


def snake_case2camelcase(word):
    return "".join(x.capitalize() or "_" for x in word.split("_"))


def format_btc_amount_as_sats(
    value: Union[float, str],
    enable_digit_formatting=False,
) -> str:
    s = "{:,.0f}".format(round(float(value) * 1e8))

    # combine the "," with the left number to an array
    array = []
    for letter in s:
        if letter == ",":
            array[-1] += letter
        else:
            array.append(letter)

    if enable_digit_formatting:
        if len(array) >= 4:
            left_index = -6 if len(array) >= 6 else -len(array)
            array[
                left_index
            ] = f'<span class="thousand-digits-in-sats-amount">{array[left_index]}'
            array[-4] = f"{array[-4]}</span>"

        left_index = -3 if len(array) >= 3 else -len(array)
        array[
            left_index
        ] = f'<span class="last-digits-in-sats-amount">{array[left_index]}'
        array[-1] = f"{array[-1]}</span>"

    return "".join(array)


def format_btc_amount(
    value: Union[float, str],
    maximum_digits_to_strip=7,
    minimum_digits_to_strip=6,
    enable_digit_formatting=True,
) -> str:
    """
    Formats the btc amount such that it can be right aligned such
    that the decimal separator will be always at the same x position.

    Stripping trailing 0's is done via just making the 0's transparent.

    Args:
        value (Union[float, str]): Will convert string to float.
            The float is expected to be in the unit (L)BTC with 8 relevant digits
        maximum_digits_to_strip (int, optional): No more than maximum_digits_to_strip
            trailing 0's will be stripped. Defaults to 7.
        minimum_digits_to_strip (int, optional): Only strip any trailing 0's if
            there are at least minimum_digits_to_strip. Defaults to 6.
        enable_digit_formatting (bool, optional): Will group the Satoshis into blocks of 3,
            e.g. 0.03 123 456, and color the blocks. Defaults to True.

    Returns:
        str: The formatted btc amount as html code.
    """
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
        # loop through the float number, e.g. 0.03 000 000, from the right and replace 0's or the '.' until you hit anything != 0
        for i in reversed(range(len(array))):
            if array[i] == "0" and len(array) - i <= maximum_digits_to_strip:
                array[
                    i
                ] = f'<span class="unselectable transparent-text">{array[i]}</span>'
                # since this digit == 0, then continue the loop and check the next digit
                continue
            # the following if branch is only relevant if last_digits_to_strip == 8, i.e. all digits can be stripped
            elif formatted_amount[i] == ".":
                array[
                    i
                ] = f'<span class="unselectable transparent-text">{array[i]}</span>'
                # since this character == '.', then the loop must be broken now
            # always break the loop. Only the digit == 0 can prevent this break
            break

    if enable_digit_formatting:
        array[-6] = f'<span class="thousand-digits-in-btc-amount">{array[-6]}'
        array[-4] = f"{array[-4]}</span>"
        array[-3] = f'<span class="last-digits-in-btc-amount">{array[-3]}'
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
