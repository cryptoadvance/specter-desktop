def str2bool(my_str):
    """returns a reasonable boolean from a string so that "False" will result in False"""
    if my_str is None:
        return False
    elif isinstance(my_str, str) and my_str.lower() == "false":
        return False
    elif bool(my_str) is False:
        return False
    else:
        return bool(my_str)
