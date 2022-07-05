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
from flask import current_app as app


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

    def __init__(self, user_manager):
        super().__init__()
        self.connections = list()
        self.admin_tokens = list()
        self.user_manager = user_manager

    def get_connection_user_tokens(self):
        return [d["user_token"] for d in self.connections]

    def get_admin_tokens(self):
        return [d["user_token"] for d in self.admin_tokens]

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

    async def send_to_websocket(self, message_dictionary, websocket):
        response = await websocket.send(
            json.dumps(self.clean_message(message_dictionary))
        )
        return response

    def clean_message(
        self, message_dictionary, keys=["user_token", "recipient_tokens"]
    ):
        new_dict = message_dictionary.copy()
        for key in keys:
            if key in new_dict:
                del new_dict[key]
        return new_dict

    def get_valid_recipients_of_message(self, message_dictionary):
        "Controls that only the admin can send to all users.  Users can only send to themselves."
        recipient_tokens = message_dictionary.get("recipient_tokens")

        possbile_recipient_tokens = [
            recipient_token
            for recipient_token in recipient_tokens
            if recipient_token in self.get_connection_user_tokens()
        ]
        logger.info(f"possbile_recipient_tokens {possbile_recipient_tokens}")
        if message_dictionary.get("user_token") in self.admin_tokens:
            valid_recipient_tokens = possbile_recipient_tokens
        else:
            valid_recipient_tokens = (
                [message_dictionary.get("user_token")]
                if message_dictionary.get("user_token") in possbile_recipient_tokens
                else []
            )

        return valid_recipient_tokens

    async def process_incoming_message(self, message_dictionary):
        logger.info(f'starting to process_incoming_message "{message_dictionary}"')
        valid_recipient_tokens = self.get_valid_recipients_of_message(
            message_dictionary
        )
        if not valid_recipient_tokens:
            logger.info(
                f'No valid_recipient_tokens found. Nowhere to send "{message_dictionary}"'
            )
            return

        await asyncio.wait(
            [
                self.send_to_websocket(
                    message_dictionary, self.get_connection(recipient_token)
                )
                for recipient_token in valid_recipient_tokens
            ]
        )

    async def _forever_listener(self, websocket, path):  # don't remove path
        try:
            async for message in websocket:  # this is an endless loop waiting for incoming websocket messages
                try:
                    logger.info(f"Do stuff with message: {message}")
                    message_dictionary = json.loads(message)
                    if message_dictionary.get("type") == "authentication":
                        await self.register(
                            message_dictionary.get("user_token"), websocket
                        )
                    else:
                        await self.process_incoming_message(message_dictionary)
                except:
                    logger.error(f"message {message} caused an error", exc_info=True)
                if self.quit:
                    break  # self.quit not working yet
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
        full_dict = message_dictionary.copy()
        full_dict["user_token"] = self.user_token
        logger.info(f"adding to queue {message_dictionary}")
        self.q.put(json.dumps(full_dict))

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


def run_server_and_client():
    client = WebsocketsClient()
    ws = WebsocketsServer(app.specter.user_manager)
    ws.set_as_admin(
        client.user_token
    )  # this ensures that this client has rights to send to other users

    ws.start()
    client.start()
    client.authenticate()
    return ws, client


if __name__ == "__main__":
    ws, client = run_server_and_client()

    # get into the server loop via a queue

    for i in range(100):
        time.sleep(2)
        client.send(
            {
                "type": "message",
                "message": f"loop {i}",
                "recipient_tokens": ws.get_connection_user_tokens(),
            }
        )

    client.quit = True
    time.sleep(2)
    ws.quit = True
