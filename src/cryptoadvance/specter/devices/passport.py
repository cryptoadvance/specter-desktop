from .keystone import Keystone


class Passport(Keystone):
    device_type = "passport"
    name = "Passport"
    icon = "img/devices/passport_icon.svg"
