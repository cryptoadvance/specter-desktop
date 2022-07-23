"""
This file enabled to keep an open websocket connection with the browser sessions.
"""
import logging, threading, time, secrets
from queue import Queue

from flask_login import current_user

logger = logging.getLogger(__name__)


import time, json
from ..helpers import robust_json_dumps


import simple_websocket, ssl


def run_websockets_server_and_client(notification_manager, user_manager, environ):
    server = SimpleWebsocketServer(notification_manager, user_manager, environ)
    client = notification_manager.set_websockets_server_and_start_client(
        server, environ
    )
    server.set_as_admin(
        client.user_token
    )  # this ensures that this client has rights to send to other users
    server.serve()  # runs forever
    logger.info(f"Stopped websockets_server with environ {environ}")

    # now I have to wait until the server is started and is ready to recieve messages
    for i in range(50):
        if server.started:
            break
        time.sleep(0.1)  # sleep for 0.1 seconds
        if i == 49:
            server.quit()
            logger.error(
                f'The server never reached the "started" state. Quitting the server and do not attempt to start the client.'
            )
            return

    client.start()
    client.authenticate()

    return server, client


def oldrun_websockets_server_and_client(ws, client):
    ws.start()
    # now I have to wait until the server is started and is ready to recieve messages
    for i in range(50):
        if ws.started:
            break
        time.sleep(0.1)  # sleep for 0.1 seconds
        if i == 49:
            ws.quit()
            logger.error(
                f'The server never reached the "started" state. Quitting the server and do not attempt to start the client.'
            )
            return

    client.port = (
        ws.port
    )  # ensure that even if the port changed in the server, the client can connect
    client.start()
    client.authenticate()


class SimpleWebsocketClient:
    """
    A forever lived websockets server in a different thread.
    The server has 2 main functions:
    1. Recieve messages from webbrowser websocket connections and call notification_manager.create_and_show
    2. Recieve messages (notifications) from python websocket connection and send them to the webbrowser websocket connections
    When registering the websocket connection, the webbrowser websocket connection has to authenticate with a user_token,
        which is checked against user_manager.....websocket_token  to make sure this is a legitimate user
    Before the python websocket connection is established, the set_as_admin method should be called to inform self that this user_token will be an admin
        Otherwise the user_token will not be found in user_manager.....websocket_token and rejected
    1.   Javascript creates a message
        ┌───────────────────────┐                           ┌───────────────────────┐
        │                       │     websocket.send        │                       │
        │  Browser javascript   ├─────────────────────────► │   WebsocketsServer    │
        │                       │                           │                       │
        └───────────────────────┘                           └───────────┬───────────┘
                                                                        │
                                                                        │ notification_manager.create_and_show
                                                                        │
                                                                        ▼
                                                            ┌───────────────────────┐
                                                            │                       │
                                                            │  NotificationManager  │
                                                            │                       │
                                                            └───────────────────────┘
    2.    A UI_Notification creates a message for the browser to show
        ┌───────────────────────┐                           ┌───────────────────────┐
        │                       │ websockets_client.send    │                       │
        │ JSConsoleNotifications├─────────────────────────► │   WebsocketsClient    │
        │                       │                           │                       │
        └───────────────────────┘                           └───────────┬───────────┘
                                                                        │
                                                                        │
                                                                        │ websockets_client.send
                                                                        │
                                                                        ▼
        ┌───────────────────────┐                           ┌───────────────────────┐
        │                       │                           │                       │
        │ Browser javascript    │     websocket.send        │                       │
        │                       │◄──────────────────────────┤  WebsocketsServer     │
        │ websocket.on_message  │                           │                       │
        │                       │                           │                       │
        └───────────────────────┘                           └───────────────────────┘
    """

    def __init__(self, environ, ssl_cert, ssl_key):
        self.protocol = "wss" if environ["wsgi.url_scheme"] == "https" else "ws"
        self.url = f"{self.protocol}://{environ['SERVER_NAME']}:{environ['SERVER_PORT']}/{environ['PATH_INFO']}"
        self.q = Queue()
        self.user_token = secrets.token_urlsafe(128)
        self._quit = False

        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl._create_unverified_context(ssl.PROTOCOL_TLS_CLIENT)
            # see https://pythontic.com/ssl/sslcontext/load_cert_chain
            self.ssl_context.load_cert_chain(certfile=ssl_cert, keyfile=ssl_key)

    def quit(self):
        super().quit()
        self.q.put("quit")

    def send(self, message_dictionary):
        self.q.put(robust_json_dumps(message_dictionary))

    def forever_function(self):
        self.websocket = simple_websocket.Client(self.url, ssl_context=self.ssl_context)

        logger.debug("Client: connected")
        while not self._quit:  #  this is an endless loop waiting for new queue items
            item = self.q.get()
            if item == "quit":
                logger.debug(f'quitting Queue loop because item == "{item}"')
                return
            self.websocket.send(robust_json_dumps(item))
            self.q.task_done()

        self.websocket.close()
        logger.debug("WebsocketsClient forever_function ended")

    def finally_at_stop(self):
        super().finally_at_stop()
        self.q.join()  # block until all tasks are done

    def authenticate(self):
        logger.debug("authenticate")
        self.send({"type": "authentication", "user_token": self.user_token})

    def start(self):
        try:
            self.thread = threading.Thread(target=self.forever_function)
            self.thread.daemon = True  # die when the main thread dies
            self.thread.start()
        finally:
            self.finally_at_stop()


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
        self.started = False

    def serve(self):
        try:
            logger.info(f"{self.__class__.__name__} started")
            self.started = True
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
