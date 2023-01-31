import logging
from importlib import import_module

import strawberry
from flask import current_app as app
from flask_apscheduler import APScheduler
from strawberry.flask.views import GraphQLView
from strawberry.tools import create_type

from cryptoadvance.specter.services.service import (
    Service,
    devstatus_alpha,
    devstatus_beta,
    devstatus_prod,
)

# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specterext.devhelp.schema import Bookmark, get_bookmarks

from .callbacks import create_graphql_schema
import typing
from .schema import create_fields

logger = logging.getLogger(__name__)


class GraphqlService(Service):
    id = "graphql"
    name = "Graphql Service"
    icon = "graphql/img/logo.svg"
    logo = "graphql/img/logo.svg"
    desc = "GraphQL queries for specter."
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.graphql.controller"
    callbacks = ["cryptoadvance.specterext.graphql.callbacks"]
    devstatus = devstatus_alpha
    isolated_client = False

    sort_priority = 2

    def callback_after_serverpy_init_app(self, scheduler: APScheduler):
        if not app.config["SPECTER_GRAPHQL_ACTIVE"]:
            return

        # The stuff coming directly from this extension
        field_list = create_fields()

        # later on, we'll do that via extenstioncallbacks
        field_list = app.specter.service_manager.execute_ext_callbacks(
            create_graphql_schema, field_list
        )

        query = create_type("Query", field_list)

        logger.info("GraphQL Query-Type Report")
        logger.info("=========================")
        logger.info(query)

        schema = strawberry.Schema(query=query)
        view = GraphQLView.as_view("graphql_view", schema=schema)

        logger.info("Activating GraphQL /graphql")
        # This doesn't work yet
        from .controller import graphql_endpoint

        # So unfortunately, we need to add the endpoint to the root
        app.add_url_rule("/graphql", view_func=view)
        app.csrf.exempt(view)
