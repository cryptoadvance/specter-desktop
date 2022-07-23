"""
This file enabled to keep an open websocket connection with the browser sessions.
"""
import logging, threading, time
from queue import Queue

from flask_login import current_user

logger = logging.getLogger(__name__)


import time, json
from ..helpers import robust_json_dumps


import simple_websocket, ssl


class SimpleWebsocketClient:
    """
    Keeps an open websocket connection to the server
    """

    def __init__(self, environ, ssl_cert, ssl_key):
        self.protocol = "wss" if environ["wsgi.url_scheme"] == "https" else "ws"
        self.url = f"{self.protocol}://{environ['SERVER_NAME']}:{environ['SERVER_PORT']}/{environ['PATH_INFO']}"

        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl._create_unverified_context(ssl.PROTOCOL_TLS_SERVER)
            # see https://pythontic.com/ssl/sslcontext/load_cert_chain
            self.ssl_context.load_cert_chain(certfile=ssl_cert, keyfile=ssl_key)

    def start(self, delay=1):
        "repeated try to start the client (can fail if the )"
        time.sleep(delay)
        logger.info(f"Connecting {self.__class__.__name__} to {self.url}")
        self.client = simple_websocket.Client(self.url, ssl_context=self.ssl_context)

    def send(self, message_dictionary):
        self.client.send(robust_json_dumps(message_dictionary))

    def delayed_start_in_new_thread(self):
        self.thread = threading.Thread(target=self.start)
        self.thread.daemon = True  # die when the main thread dies
        self.thread.start()


class SimpleWebsocketServer:
    def __init__(self, notification_manager, user_manager, environ):
        if not notification_manager:
            logger.warning(
                f"Could not start websocket server because notification_manager = {notification_manager}"
            )
            return
        print(environ)
        self.protocol = "wss" if environ["wsgi.url_scheme"] == "https" else "ws"
        self.port = environ["SERVER_PORT"]
        self.route = environ["PATH_INFO"]
        self.server = simple_websocket.Server(environ)
        self.admin_tokens = list()
        self.notification_manager = notification_manager
        self.user_manager = user_manager

    def serve(self):
        try:
            logger.info(f"Websocket server started")
            while True:
                data = self.server.receive()
                try:
                    message_dictionary = json.loads(data)
                except:
                    continue
                print(message_dictionary)
                self.create_notification(message_dictionary, current_user)
        except simple_websocket.ConnectionClosed:
            logger.info(f"Websocket connection of {self.user} closed")
        return ""

    def set_as_admin(self, user_token):
        new_entry = {"user_token": user_token}
        logger.debug(f"set_as_admin {new_entry}")
        self.admin_tokens.append(new_entry)

    def remove_admin(self, user_token):
        logger.debug(f"remove_admin {user_token}")
        self.admin_tokens = [
            d for d in self.admin_tokens if d["user_token"] != user_token
        ]

    def create_notification(self, message_dictionary, user):
        """Creates a notification based on the title, options contained in message_dictionary
        Example of message_dictionary:

            {
                'title' : title,
                'options':{
                    'timeout' : timeout,
                    'notification_type' : notification_type,
                    'target_uis' : target_uis,
                    'body' : body,
                    'image' : image_url,
                    'icon' : icon,
                }
            }
            Only 'title' is mandatory
            The options are the optional arguments of Notification()
        """
        if "title" not in message_dictionary:
            logger.warning(f"No title in {message_dictionary}")
            return

        title = message_dictionary["title"]
        options = message_dictionary.get("options", {})

        logger.debug(
            f"create_notification with title  {title}, user {self.user} and options {options}"
        )

        notification = self.notification_manager.create_and_show(
            title,
            user,
            **options,
        )
        return notification

    async def send_to_websockets(self, message_dictionary, admin_token):
        """
        This sends out messages to the connected websockets, which are associated with message_dictionary['options']['user_id']
        This method shall only called by an admin user
        """
        assert admin_token in self.get_admin_tokens()

        logger.debug(f'send_to_websockets "{message_dictionary}"')

        recipient_user = self.user_manager.get_user(
            message_dictionary["options"]["user_id"]
        )
        if not recipient_user:
            logger.warning(
                f"No recipient_user for recipient_user_id {recipient_user.name} could be found"
            )
            return

        response = self.server.send(robust_json_dumps(message_dictionary))
        return response
