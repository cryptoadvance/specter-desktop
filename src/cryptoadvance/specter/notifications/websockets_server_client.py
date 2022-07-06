import logging
from queue import Queue

logger = logging.getLogger(__name__)

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


import secrets
import asyncio
import time, json
import websockets
import threading
from ..helpers import robust_json_dumps


class WebsocketsBase:
    """
    A base class that keeps a websockets connection or server running forever in a different thread
    """

    def __init__(self):
        self.domain = "localhost"
        self.port = "5086"
        self.quit = False

    def forever_function(self):
        "This is the function that will contain an endless loop"
        pass

    def _forever_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.forever_function())
        loop.run_forever()  # this is needed for the server, and does nothing for the client
        loop.close()

    def finally_at_stop(self):
        pass

    def start(self):
        try:
            t = threading.Thread(target=self._forever_thread)
            t.start()
        finally:
            self.finally_at_stop()


class WebsocketsServer(WebsocketsBase):
    """
    A forever lived websockets server in a different thread
    """

    def __init__(self, user_manager, notification_manager):
        super().__init__()
        self.connections = list()
        self.admin_tokens = list()
        self.user_manager = user_manager
        self.notification_manager = notification_manager

    def get_connection_user_tokens(self):
        return [d["user_token"] for d in self.connections]

    def get_admin_tokens(self):
        return [d["user_token"] for d in self.admin_tokens]

    def get_token_of_websocket(self, websocket):
        for d in self.connections:
            if d["websocket"] == websocket:
                return d["user_token"]

    def get_connection(self, user_token):
        for d in self.connections:
            if d["user_token"] == user_token:
                return d["websocket"]

    def user_of_user_token(self, user_token):
        for u in self.user_manager.users:
            if u.websocket_token == user_token:
                return u

    def set_as_admin(self, user_token):
        new_entry = {"user_token": user_token}
        logger.info(f"set_as_admin {new_entry}")
        self.admin_tokens.append(new_entry)

    def remove_admin(self, user_token):
        logger.info(f"remove_admin {user_token}")
        self.admin_tokens = [
            d for d in self.admin_tokens if d["user_token"] != user_token
        ]

    async def register(self, user_token, websocket):
        if not user_token:
            logger.warning(f"no user_token given")
            return

        logger.info(f"register  {user_token},  admins = {self.get_admin_tokens()}")
        if user_token in self.get_admin_tokens():
            logger.info(f"register websocket connection for user with ADMIN rights")
        else:
            user = self.user_of_user_token(user_token)
            # If it is not an admin AND the token is unknown, then reject connection
            if not user:
                logger.warning(f"user_token {user_token} not found in users")
                return
            logger.info(
                f"register websocket connection for flask user '{user.username}'"
            )

        self.connections.append({"user_token": user_token, "websocket": websocket})

    async def unregister(self, websocket):
        logger.info(f"unregister {websocket}")
        self.connections = [d for d in self.connections if d["websocket"] != websocket]

    def create_notification(self, message_dictionary, user_token):
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

        # Identify the user_token (and then the user_id) based on the websocket connection.
        user_id = (
            self.user_of_user_token(user_token).username
            if self.user_of_user_token(user_token)
            else None
        )
        if not user_id:
            logger.warning(f"No user_id found for user_token {user_token}.")

            # Admins should not create notifications here, but in the Notification Manager
            assert user_token not in self.get_admin_tokens()
            return

        logger.info(
            f"create_notification with title  {title}, user_id {user_id} and options {options}"
        )

        notification = self.notification_manager.create_and_show(
            title,
            user_id,
            **options,
        )

    async def send_to_websockets(self, message_dictionary, admin_token):
        """
        This sends out messages to the connected websockets, which are associated with message_dictionary['options']['user_id']
        This method shall only called by an admin user
        """
        assert admin_token in self.get_admin_tokens()

        logger.info(f'send_to_websockets "{message_dictionary}"')

        recipient_user_id = self.get_connection(
            message_dictionary["options"]["user_id"]
        )
        recipient_user = self.user_manager.get_user(recipient_user_id)
        if not recipient_user:
            logger.warning(
                f"No recipient_user for recipient_user_id {recipient_user_id} could be found"
            )
            return

        websocket = self.get_connection(recipient_user.websocket_token)
        if not websocket:
            logger.warning(
                f"No websocket for this recipient_user.websocket_token could be found"
            )
            return

        response = await websocket.send(robust_json_dumps(message_dictionary))
        return response

    async def process_incoming_message(self, message_dictionary, websocket):
        """
        This listens to messages. They can come from connections with and without admin tokens.

        If this is a websocket authentication, it will so self.register,
        otherwise just forward to to the notification_manager via self.create_notification
        """

        user_token = self.get_token_of_websocket(websocket)

        if message_dictionary.get("type") == "authentication":
            await self.register(message_dictionary.get("user_token"), websocket)
        elif user_token and user_token in self.get_admin_tokens():
            logger.info(
                f"message from user {user_token} with admin_token recieved. Sending to websockets"
            )
            await self.send_to_websockets(message_dictionary, user_token)
        else:
            logger.info(
                f"message from user {user_token} recieved. Creating Notification"
            )
            self.create_notification(message_dictionary, user_token)

    async def _forever_listener(self, websocket, path):  # don't remove path
        try:
            async for message in websocket:  # this is an endless loop waiting for incoming websocket messages
                try:
                    logger.info(f"Do stuff with message: {message}")
                    message_dictionary = json.loads(message)
                    await self.process_incoming_message(message_dictionary, websocket)
                except:
                    logger.error(f"message {message} caused an error", exc_info=True)
                if self.quit:
                    break  # self.quit not working yet
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning("Server Connection dropped")
        finally:
            await self.unregister(websocket)

    def forever_function(self):
        return websockets.serve(self._forever_listener, self.domain, self.port)


class WebsocketsClient(WebsocketsBase):
    """
    Keeps an open websocket connection to the server in a different thread.
    If  a message is entered into the Queue (self.q), then it will be picked up and send to the websockets server
    """

    def __init__(self):
        super().__init__()
        self.q = Queue()
        self.user_token = secrets.token_urlsafe(128)

    def send(self, message_dictionary):
        self.q.put(robust_json_dumps(message_dictionary))

    async def _send_message_to_server(self, message, websocket, expected_answers=0):
        answers = []
        logger.info(f"_send_message_to_server {message}")
        await websocket.send(message)
        for i in range(expected_answers):
            answer = await websocket.recv()
            answers.append(answer)
            logger.info(f"Client: Answer {i} from server: {answer}")
        return answers

    async def forever_function(self):
        async with websockets.connect(f"ws://{self.domain}:{self.port}") as websocket:
            logger.info("Client: connected")
            while not self.quit:  #  this is an endless loop waiting for new queue items
                item = self.q.get()
                await self._send_message_to_server(item, websocket)
                self.q.task_done()

    def finally_at_stop(self):
        self.q.join()  # block until all tasks are done

    def authenticate(self):
        logger.info("authenticate")
        self.send({"type": "authentication", "user_token": self.user_token})


def run_server_and_client(user_manager, notification_manager):
    client = WebsocketsClient()
    ws = WebsocketsServer(user_manager, notification_manager)
    ws.set_as_admin(
        client.user_token
    )  # this ensures that this client has rights to send to other users

    ws.start()
    client.start()
    client.authenticate()
    return ws, client
