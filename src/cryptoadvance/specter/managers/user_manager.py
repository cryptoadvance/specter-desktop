import os
import json
import logging
from ..persistence import read_json_file, write_json_file
from ..user import User, hash_password
from flask_login import current_user

logger = logging.getLogger(__name__)


class UserManager:
    """
    The UserManager can manage users
    """

    # of them via json-files in an empty data folder
    def __init__(self, specter):
        self.specter = specter
        self.data_folder = specter.data_folder
        self.update()

    @property
    def users_file(self):
        return os.path.join(self.data_folder, "users.json")

    def load_users(self):
        # if users.json file exists - load from it
        if os.path.isfile(self.users_file):
            users = read_json_file(self.users_file)
        # otherwise - create one and assign unique id
        else:
            users = [
                {
                    "id": "admin",
                    "username": "admin",
                    "password": hash_password("admin"),
                    "is_admin": True,
                }
            ]
        # convert to User instances
        self.users = [User.from_json(u, self.specter) for u in users]
        if not os.path.isfile(self.users_file):
            self.save()

    def update(self):
        self.load_users()

    def save(self):
        users_json = [u.json for u in self.users]
        write_json_file(users_json, self.users_file)

    def add_user(self, user):
        """Adds a User-Object to the list"""
        if user not in self.users:
            self.users.append(user)
            user.manager = self
        self.save()  # save files
        user.check()
        return self.get_user(user)

    @property
    def admin(self):
        """There is always one admin"""
        for u in self.users:
            if u.is_admin:
                return u

    def get_user(self, user=None):
        """
        Converts from flask_login user to a User in the system.
        Admin by default.
        """
        # get by string
        if user is None:
            user = current_user
        if isinstance(user, str):
            return self.get_by_uid(user)
        if user and not user.is_anonymous:
            if user in self.users:
                return self.get_by_uid(user.id)
        return self.admin

    def get_user_by_username(self, username):
        for u in self.users:
            if u.username == username:
                return u

    @property
    def user(self):
        """User in current context, admin if no context"""
        return self.get_user(current_user)

    def get_by_uid(self, uid):
        for u in self.users:
            if u.id == uid:
                return u
        logger.error("Could not find user %s" % uid)

    def delete_user(self, user):
        self.users.remove(user)
        self.save()
