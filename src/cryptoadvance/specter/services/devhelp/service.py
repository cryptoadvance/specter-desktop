from ..service import Service, devstatus_alpha


class DevhelpService(Service):
    id = "devhelp"
    name = "Development Helper"
    icon = "img/ghost.png"
    logo = "img/ghost.png"
    desc = "Where Development gets easier."
    has_blueprint = True
    devstatus = devstatus_alpha

    sort_priority = 2
