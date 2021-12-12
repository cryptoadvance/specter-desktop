from ..service import Service, devstatus_beta


class DummyService2(Service):
    id = "dummyservice2"
    name = "Placeholder"
    icon = "img/dummyservice2_icon.png"
    logo = "img/dummyservice2_icon.png"
    desc = "More integrations coming soon!"
    has_blueprint = True
    devstatus = devstatus_beta

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 3
