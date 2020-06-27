from flask_login import UserMixin
from .helpers import get_users_json, save_users_json
from .specter_error import SpecterError

class User(UserMixin):
    def __init__(self, id, username, password, config, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.config = config
        self.is_admin = is_admin

    @classmethod
    def from_json(cls, user_dict):
        # TODO: Unify admin in backwards compatible way
        try:
            if not user_dict['is_admin']:
                return cls(user_dict['id'], user_dict['username'], user_dict['password'], user_dict['config'])
            else:
                return cls(user_dict['id'], user_dict['username'], user_dict['password'], {}, is_admin=True)
        except:
            raise SpecterError('Unable to parse user JSON.')

    @classmethod
    def get_user(cls, specter, id):
        users = get_users_json(specter)
        for user_dict in users:
            user = User.from_json(user_dict)
            if user.id == id:
                return user
    
    @classmethod
    def get_user_by_name(cls, specter, username):
        users = get_users_json(specter)
        for user_dict in users:
            user = User.from_json(user_dict)
            if user.username == username:
                return user

    @property
    def json(self):
        user_dict = {
            'id': self.id,
            'username': self.username,
            'password': self.password,
            'is_admin': self.is_admin
        }
        if not self.is_admin:
            user_dict['config'] = self.config
        return user_dict

    def save_info(self, specter):
        users = get_users_json(specter)
        existing = False
        for i in range(len(users)):
            if users[i]['id'] == self.id:
                users[i] = self.json
                existing = True
        if not existing:
            users.append(self.json)
        
        save_users_json(specter, users)

    def set_explorer(self, specter, explorer):
        self.config['explorers'][specter.chain] = explorer
        self.save_info(specter)

    def set_hwi_bridge_url(self, specter, url):
        self.config['hwi_bridge_url'] = url
        self.save_info(specter)
