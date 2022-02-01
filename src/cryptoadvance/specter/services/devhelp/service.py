from ..service import Service, devstatus_alpha


class DevhelpService(Service):
    id = "devhelp"
    name = "Development Helper"
    icon = "devhelp/img/orange-wrench.png"
    logo = "devhelp/img/orange-wrench.png"
    desc = "Wrenches at work."
    has_blueprint = True
    devstatus = devstatus_alpha

    sort_priority = 2
