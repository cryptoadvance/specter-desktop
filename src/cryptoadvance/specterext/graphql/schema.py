from flask import current_app as app
from cryptoadvance.specter.managers.user_manager import UserManager

import typing
import strawberry
from typing import List
import json
import os
import logging

logger = logging.getLogger(__name__)


@strawberry.type
class User:
    username: str


def get_users() -> List[User]:
    um: UserManager = app.specter.user_manager
    um.users
    listOfUsers = []
    for item in um.users:
        u = User(username=item.username)
        listOfUsers.append(u)
    return listOfUsers


def create_fields():
    return [strawberry.field(name="users", resolver=get_users)]
