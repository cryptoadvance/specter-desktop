"""
This file enabled to keep an open websocket connection with the browser sessions.
"""
import logging, threading, time, secrets
import time, json
from cryptoadvance.specter.util.common import robust_json_dumps
import simple_websocket, ssl
from cryptoadvance.specter.specter_error import SpecterError
from datetime import datetime

logger = logging.getLogger(__name__)
IGNORE_NOTIFICATION_TITLE = "IGNORE_NOTIFICATION_TITLE"


class WebsocketServer:
    """
    A forever lived websockets server in a different thread.
    The server has 2 main functions:
    1. Recieve messages from webbrowser websocket connections and call notification_manager.create_and_show
    2. Recieve messages (notifications) from python websocket connection (broadcaster) and send them to the webbrowser websocket connections
    Each message must contain a user_token, which is checked against user_manager.user.websocket_token to make sure this is a legitimate user.
    Otherwise the user_token will not be found in user_manager.user.websocket_token and rejected.
    Before the python websocket connection is established, the set_as_broadcaster method should be called to inform self that this user_token will be a broadcaster
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

    def __init__(self, notification_manager, verbose_debug=False):
        logger.info(f"Create {self.__class__.__name__}")

        # a broadcaster has special rights, and can send potentially harmful messages to the websocket server,
        # such at a Notification("quit_server"), which will quit the server
        # It is also the only connection which makes the server send notifications to other websocket connections
        self.broadcaster_tokens = list()
        # self.connections matches user_tokens to websocket connections, such that a
        # Notification can be sent to all websocket connections that are associated to this user_tokens
        self.connections = list()
        self.notification_manager = notification_manager
        self.verbose_debug = verbose_debug

    def __str__(self):
        return str(self.__dict__)

    def get_broadcaster_tokens(self):
        return [d["user_token"] for d in self.broadcaster_tokens]

    def _get_connection_dict_of_websocket(self, websocket):
        for d in self.connections:
            if d["websocket"] == websocket:
                return d
        return None

    def get_token_of_websocket(self, websocket):
        connection_dict = self._get_connection_dict_of_websocket(websocket)
        if not connection_dict:
            logger.warning(f"user_token of websocket {websocket} could not be found.")
            return
        return connection_dict["user_token"]

    def get_connections_by_token(self, user_token):
        connections = []
        for d in self.connections:
            if d["user_token"] == user_token:
                connections.append(d["websocket"])
        return connections

    def get_user_of_user_token(self, user_token):
        for (
            known_username,
            known_token,
        ) in self.notification_manager.websocket_tokens.items():
            if known_token == user_token:
                return known_username
        return None

    def set_as_broadcaster(self, user_token):
        new_entry = {"user_token": user_token}
        logger.debug(f"set_as_broadcaster {f'...{user_token[-5:]}'}")
        self.broadcaster_tokens.append(new_entry)

    def remove_broadcaster(self, user_token):
        logger.debug(f"remove_broadcaster ...{user_token[-5:]}")
        self.broadcaster_tokens = [
            d for d in self.broadcaster_tokens if d["user_token"] != user_token
        ]

    def _register(self, user_token, websocket):
        if not user_token:
            logger.warning(f"no user_token given")
            return

        d = {
            "user_token": user_token,
            "websocket": websocket,
            "opening_time": datetime.now(),
        }

        # check if this connection exists already
        connection_dict = self._get_connection_dict_of_websocket(websocket)
        if connection_dict and connection_dict["user_token"] == user_token:
            # no need to add the connection multiple times if (websocket, user_token) are identical
            return

        if user_token in self.get_broadcaster_tokens():
            logger.info(
                f"python-websocket-client --> python-websocket-server was first used and registered."
            )
        else:
            user = self.get_user_of_user_token(user_token)
            # If it is not a broadcaster AND the token is unknown, then reject connection
            if not user:
                logger.warning(f"user_token ...{user_token[-5:]} not found in users")
                return
            logger.info(
                f"python-websocket-server --> javascript websocket-client  for flask user '{user}'  was first used and registered."
            )

        self.connections.append(d)
        if self.verbose_debug:
            logger.debug(self.connection_report())

    def _unregister(self, websocket):
        connection_dict = self._get_connection_dict_of_websocket(websocket)
        if not connection_dict:
            logger.warning(
                f"_unregister failed, because {websocket} could not be found in self.connections."
            )
            return
        user_token = connection_dict["user_token"]
        user = self.get_user_of_user_token(user_token)

        username = (
            user
            if user
            else (
                "Python broadcaster Client"
                if user_token in self.get_broadcaster_tokens()
                else "unknown"
            )
        )
        self.connections = [d for d in self.connections if d["websocket"] != websocket]
        logger.debug(
            f"Unregistered {websocket} belonging to {username}, started at {connection_dict['opening_time']}"
        )
        if self.verbose_debug:
            logger.debug(self.connection_report())

    def connection_report(self):
        s = f"{len(self.connections)} open connections:\n"
        for i, connection_dict in enumerate(self.connections):
            simplified_dict = connection_dict.copy()
            simplified_dict["opening_time"] = connection_dict[
                "opening_time"
            ].isoformat()
            simplified_dict["user_token"] = f"...{connection_dict['user_token'][-5:]}"
            simplified_dict["user"] = (
                None
                if connection_dict["user_token"] in self.get_broadcaster_tokens()
                else self.get_user_of_user_token(connection_dict["user_token"])
            )
            simplified_dict["broadcaster"] = (
                connection_dict["user_token"] in self.get_broadcaster_tokens()
            )
            s += f"{i}: {simplified_dict}\n"
        return s

    def serve(self, environ, ping_interval=30):
        """
        Start a server. This is an endless loop.
        It will automatically detect and close unresponsive connections.

        Args:
            environ (_type_): a flask/werkzeug environ
        """
        # ping_interval!=None ensures closing of connections where there is no counterpart any more
        websocket = simple_websocket.Server(environ, ping_interval=ping_interval)
        try:
            logger.info(
                f"Started websocket connection {websocket} between the server and a new client"
            )
            while True:
                # timeout is needed here otherwise the simple_websocket.Server ping_interval does not work
                data = websocket.receive(timeout=ping_interval)
                # If the timeout was triggered then data=None, and it should just restart receiving
                if not data:
                    continue
                try:
                    message_dictionary = json.loads(data)
                except:
                    logger.warning(f"Could not decode the json data in {data}")
                    continue

                self._register(message_dictionary.get("user_token"), websocket)

                preprocessed_instruction = self._preprocess(message_dictionary)
                if preprocessed_instruction == "quit":
                    logger.debug("quit_server was called.")
                    break
                elif preprocessed_instruction == "continue":
                    continue

                self._process_incoming_message(message_dictionary)
        except simple_websocket.ConnectionClosed:
            logger.info(f"Websocket connection {websocket} closed")
        finally:
            self._unregister(websocket)

        return ""

    def _preprocess(self, message_dictionary):
        """
        Processes special commands to manipulate the server.
        A title 'quit_server' sent from and broadcaster can make the websocket connection close.
        """
        user_token = message_dictionary.get("user_token")
        # if there was no user_token given, then prevent any further action with this message
        if not user_token:
            logger.warning(
                f"Notification {message_dictionary} did not contain a user_token. Disregarding notification."
            )
            return "continue"
        if message_dictionary.get("title") == IGNORE_NOTIFICATION_TITLE:
            return "continue"
        if message_dictionary.get("title") == "quit_server":
            # Accept the command from an broadcaster, but disregard the command from a user
            return "quit" if user_token in self.get_broadcaster_tokens() else "continue"

    def _process_incoming_message(self, message_dictionary):
        """
        This listens to messages. They can come from connections with and without broadcaster tokens.
        If this is a websocket authentication, it will so self._register,
        otherwise just forward to to the notification_manager via self._create_notification
        """

        user_token = message_dictionary.get("user_token")
        user = self.get_user_of_user_token(user_token)

        if user_token in self.get_broadcaster_tokens():
            if self.verbose_debug:
                logger.debug(
                    f"message from user with broadcaster_token recieved. Sending to websockets"
                )
            self._send_to_websockets(message_dictionary, user_token)
        elif user:
            if self.verbose_debug:
                logger.debug(f"message from user recieved. Creating Notification")
            self._create_notification(message_dictionary, user)
        else:
            logger.warning(
                f"user_token ...{user_token[-5:]} is not valid. Please provide a user_token in the message"
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

        if self.verbose_debug:
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
                if self.verbose_debug:
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
        This method shall only called by a broadcaster
        """
        assert broadcaster_token in self.get_broadcaster_tokens()

        if not message_dictionary["options"]["user_id"]:
            logger.warning("No options.user_id given")
            return

        user_token = self.notification_manager.get_websocket_token(
            message_dictionary["options"]["user_id"]
        )
        connections = self.get_connections_by_token(user_token)
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

    def __init__(self, host, port, path, ssl_cert, ssl_key, verbose_debug=False):
        self.protocol = "wss" if ssl_cert and ssl_cert else "ws"
        self.url = f"{self.protocol}://{host}:{port}/{path}"
        self.user_token = secrets.token_urlsafe(128)

        self.verbose_debug = verbose_debug
        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl._create_unverified_context(ssl.PROTOCOL_TLS_CLIENT)
            # see https://pythontic.com/ssl/sslcontext/load_cert_chain
            self.ssl_context.load_cert_chain(certfile=ssl_cert, keyfile=ssl_key)

    def __str__(self):
        return str(self.__dict__)

    def send(self, message_dictionary):
        message_dictionary["user_token"] = self.user_token
        if self.verbose_debug:
            logger.debug(f"{self.__class__.__name__} sending {message_dictionary}")
        self.websocket.send(robust_json_dumps(message_dictionary))

    def start_client_server_in_other_thread(self):
        delay = 0.1
        success = False
        retries = 100
        for i in range(retries):
            try:
                # if successfull this process will run forever. This is why this should run in a dedicated thread.
                # Only for the first connection, this will not block this thread.
                # In practice it doesn't make any difference, as long as this function is run in a separate thread.
                logger.info(f"Connecting {self.__class__.__name__}")
                self.websocket = simple_websocket.Client(
                    self.url, ssl_context=self.ssl_context
                )
                success = True
                logger.debug(
                    f"Created {self.__class__.__name__} connection to url {self.url}"
                )
                self._initialize_connection_to_server()
                break
            except ConnectionRefusedError:
                logger.debug(
                    f"Connection of {self.__class__.__name__} to websocket-server failed in loop {i}. Retrying in {delay}s..."
                )
                time.sleep(delay)
        if not success:
            logger.error(
                f"Connection of {self.__class__.__name__} to websocket-server failed despite {retries} attempts."
                f"\nConfiguration: {self}"
            )

    def start(self):
        self.thread = threading.Thread(target=self.start_client_server_in_other_thread)
        self.thread.daemon = True  # die when the main thread dies
        self.thread.start()

    def is_connected(self):
        return bool(self.websocket)

    def _close(self):
        self.websocket.close()
        self.websocket = None

    def quit_server(self):
        "Sends the command 'quit_server' to the websocket server. which then shuts down the connection."
        message_dictionary = {"title": "quit_server"}
        self.send(message_dictionary)
        self._close()

    def _initialize_connection_to_server(self):
        "Sends a message to the server, that does nothing, but enables the server to register the user_token to the websocket_client"
        self.send({"title": IGNORE_NOTIFICATION_TITLE})
