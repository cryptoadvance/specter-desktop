"""
This file enabled to keep an open websocket connection with the browser sessions.
"""
import logging, threading, time, secrets
import time, json
from ..helpers import robust_json_dumps
import simple_websocket, ssl


logger = logging.getLogger(__name__)


class WebsocketServer:
    """
    A forever lived websockets server in a different thread.
    The server has 2 main functions:
    1. Recieve messages from webbrowser websocket connections and call notification_manager.create_and_show
    2. Recieve messages (notifications) from python websocket connection and send them to the webbrowser websocket connections
    Each message must contain a user_token, which is checked against user_manager.user.websocket_token to make sure this is a legitimate user
    Before the python websocket connection is established, the set_as_broadcaster method should be called to inform self that this user_token will be an admin
        Otherwise the user_token will not be found in user_manager.user.websocket_token and rejected
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

    def __init__(self, notification_manager, user_manager):
        logger.info(f"Create {self.__class__.__name__}")

        self.broadcaster_tokens = list()
        self.connections = list()
        self.notification_manager = notification_manager
        self.user_manager = user_manager

    def get_broadcaster_tokens(self):
        return [d["user_token"] for d in self.broadcaster_tokens]

    def get_token_of_websocket(self, websocket):
        for d in self.connections:
            if d["websocket"] == websocket:
                return d["user_token"]

    def get_connections_by_token(self, user_token):
        connections = []
        for d in self.connections:
            if d["user_token"] == user_token:
                connections.append(d["websocket"])
        return connections

    def get_user_of_user_token(self, user_token):
        for u in self.user_manager.users:
            if u.websocket_token == user_token:
                return u.username

    def set_as_broadcaster(self, user_token):
        new_entry = {"user_token": user_token}
        logger.debug(f"set_as_broadcaster {new_entry}")
        self.broadcaster_tokens.append(new_entry)

    def remove_broadcaster(self, user_token):
        logger.debug(f"remove_broadcaster {user_token}")
        self.broadcaster_tokens = [
            d for d in self.broadcaster_tokens if d["user_token"] != user_token
        ]

    def _register(self, user_token, websocket):
        if not user_token:
            logger.warning(f"no user_token given")
            return

        d = {"user_token": user_token, "websocket": websocket}
        if d in self.connections:
            # no need to add the connection multiple times
            return

        if user_token in self.get_broadcaster_tokens():
            logger.info(
                f"python-websocket-client --> python-websocket-server was first used and registered."
            )
        else:
            user = self.get_user_of_user_token(user_token)
            # If it is not an admin AND the token is unknown, then reject connection
            if not user:
                logger.warning(f"user_token {user_token} not found in users")
                return
            logger.info(
                f"python-websocket-server --> javascript websocket-client  for flask user '{user}'  was first used and registered."
            )

        self.connections.append({"user_token": user_token, "websocket": websocket})

    def _unregister(self, websocket):
        user_token = self.get_token_of_websocket(websocket)
        user = self.get_user_of_user_token(user_token)

        username = (
            user
            if user
            else (
                "Python ADMIN Client"
                if user_token in self.get_broadcaster_tokens()
                else "unknown"
            )
        )
        logger.debug(f"_unregister {websocket} belonging to {username}")
        self.connections = [d for d in self.connections if d["websocket"] != websocket]

    def serve(self, environ):
        "Start a server. This is an endless loop."
        websocket = simple_websocket.Server(environ)
        try:
            logger.info(
                f"Started websocket connection {websocket} between the server and a new client"
            )
            while True:
                data = websocket.receive()
                try:
                    message_dictionary = json.loads(data)
                except:
                    continue

                preprocessed_instruction = self._preprocess(message_dictionary)
                if preprocessed_instruction == "quit":
                    logger.debug("quit_server was called.")
                    break
                elif preprocessed_instruction == "continue":
                    continue

                self._register(message_dictionary.get("user_token"), websocket)
                self._process_incoming_message(message_dictionary)
        except simple_websocket.ConnectionClosed:
            logger.info(f"Websocket connection {websocket} closed")
        finally:
            self._unregister(websocket)

        return ""

    def _preprocess(self, message_dictionary):
        """
        Processes special commands to manipulate the server.
        A title 'quit_server' sent from and admin can make the websocket connection close.
        """
        user_token = message_dictionary.get("user_token")
        if message_dictionary.get("title") == "quit_server":
            # Accept the command from an admin, but disregard the command from a user
            return "quit" if user_token in self.get_broadcaster_tokens() else "continue"

    def _process_incoming_message(self, message_dictionary):
        """
        This listens to messages. They can come from connections with and without admin tokens.
        If this is a websocket authentication, it will so self._register,
        otherwise just forward to to the notification_manager via self._create_notification
        """

        user_token = message_dictionary.get("user_token")
        user = self.get_user_of_user_token(user_token)

        if user_token in self.get_broadcaster_tokens():
            logger.debug(
                f"message from user with broadcaster_token recieved. Sending to websockets"
            )
            self._send_to_websockets(message_dictionary, user_token)
        elif user:
            logger.debug(f"message from user recieved. Creating Notification")
            self._create_notification(message_dictionary, user)
        else:
            logger.warning(
                "user_token {user_token} is not valid. Please provide a user_token in the message"
            )

    def _create_notification(self, message_dictionary, user):
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
            f"_create_notification with title  {title}, user {user, type(user)} and options {options}"
        )

        notification = self.notification_manager.create_and_show(
            title,
            user,
            **options,
        )
        return notification

    def _send(self, websocket, message_dictionary):
        "Starts a new thread and sends the data to websocket"

        def target():
            try:
                logger.debug(
                    f"_send_to_websockets  {websocket} message: {message_dictionary}"
                )
                websocket.send(robust_json_dumps(message_dictionary))
            except simple_websocket.ConnectionClosed:
                self._unregister(websocket)

        thread = threading.Thread(target=target)
        thread.daemon = True  # die when the main thread dies
        thread.start()
        thread.join()

    def _send_to_websockets(self, message_dictionary, broadcaster_token):
        """
        This sends out messages to the connected websockets, which are associated with message_dictionary['options']['user_id']
        This method shall only called by an admin user
        """
        assert broadcaster_token in self.get_broadcaster_tokens()

        recipient_user = self.user_manager.get_user(
            message_dictionary["options"]["user_id"]
        )
        if not recipient_user:
            logger.warning(
                f"No recipient_user for recipient_user_id {recipient_user.name} could be found"
            )
            return

        connections = self.get_connections_by_token(recipient_user.websocket_token)
        if not connections:
            logger.warning(
                f"No websocket for this recipient_user.websocket_token could be found"
            )
            return
        for websocket in connections:
            self._send(websocket, message_dictionary)


class WebsocketClient:
    """
    Connects to the WebsocketServer; and then the self.send method can be used to send messages to the WebsocketServer


    To ensure this client is allowed to broadcast notifications to all
    websocket connections of the server we need to set
        websockets_server.set_as_broadcaster(websockets_client.user_token)
    """

    def __init__(self, host, port, path, ssl_cert, ssl_key):
        self.protocol = "wss" if ssl_cert and ssl_cert else "ws"
        self.url = f"{self.protocol}://{host}:{port}/{path}"
        self.user_token = secrets.token_urlsafe(128)

        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl._create_unverified_context(ssl.PROTOCOL_TLS_CLIENT)
            # see https://pythontic.com/ssl/sslcontext/load_cert_chain
            self.ssl_context.load_cert_chain(certfile=ssl_cert, keyfile=ssl_key)

    def send(self, message_dictionary):
        message_dictionary["user_token"] = self.user_token
        logger.debug(f"{self.__class__.__name__} sending {message_dictionary}")
        self.websocket.send(robust_json_dumps(message_dictionary))

    def start_client_server_in_other_thread(self):
        delay = 0.1
        for i in range(100):
            time.sleep(delay)
            try:
                # if successfull this process will run forever. This is why this should run in a dedicated thread.
                # Only for the first connection, this will not block this thread.
                # In practice it doesn't make any difference, as long as this function is run in a separate thread.
                logger.info(f"Connecting {self.__class__.__name__}")
                self.websocket = simple_websocket.Client(
                    self.url, ssl_context=self.ssl_context
                )
                break
            except ConnectionRefusedError:
                logger.debug(
                    f"Connection of {self.__class__.__name__} to websocket-server failed in loop {i}. Retrying in {delay}s..."
                )

    def start(self):
        self.thread = threading.Thread(target=self.start_client_server_in_other_thread)
        self.thread.daemon = True  # die when the main thread dies
        self.thread.start()

    def quit_server(self):
        "Sends the command 'quit_server' to the websocket server. which then shuts down the connection."
        message_dictionary = {"title": "quit_server"}
        self.send(message_dictionary)
