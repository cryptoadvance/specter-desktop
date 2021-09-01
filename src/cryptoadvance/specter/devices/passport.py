from . import DeviceTypes
from .keystone import Keystone


class Passport(Keystone):
    device_type = DeviceTypes.PASSPORT
    name = "Passport"
    icon = "passport_icon.svg"
