from cryptoadvance.specter.services.callbacks import Callback


class create_graphql_schema(Callback):
    """
    Gives you the ability to add to the GraphQL schema
    example:
    def callback_create_graphql_schema(self, field_list):
        # Add your fields to the Schema like this::
        field_list.append(strawberry.field(name="bookmarks", resolver=get_bookmarks))
        return field_list
    """

    id = "create_graphql_schema"
    return_style = "middleware"
