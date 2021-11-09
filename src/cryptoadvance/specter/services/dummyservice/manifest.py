from ..service_manager import Service


class DummyService(Service):
    id = "dummyservice"
    name = "dummyservice"
    logo = ""
    desc = "Does nothing but can be switched on or off"
    has_blueprint = False
