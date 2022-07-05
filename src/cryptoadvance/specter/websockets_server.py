import logging
from queue import Queue
from urllib import response

logger = logging.getLogger(__name__)


import secrets
import asyncio
import time, json
import websockets
import threading


class WebsocketsBase:
    """
    A base class that keeps a websockets connection or server running forever in a different thread
    """

    def __init__(self):
        self.domain = "localhost"
        self.port = "5051"
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

    def __init__(self):
        super().__init__()
        self.connections = list()
        self.admin_tokens = list()

    def get_connection_user_tokens(self):
        return [d["user_token"] for d in self.connections]

    def get_connection(self, user_token):
        for d in self.connections:
            if d["user_token"] == user_token:
                return d["websocket"]

    async def register_internal_token(self, user_token):
        new_entry = {"user_token": user_token}
        print(f"register_internal_token {new_entry}")
        self.admin_tokens.append(new_entry)

    async def unregister_internal_token(self, user_token):
        print(f"unregister {user_token}")
        self.admin_tokens = [
            d for d in self.admin_tokens if d["user_token"] != user_token
        ]

    async def register(self, user_token, websocket):
        new_entry = {"user_token": user_token, "websocket": websocket}
        print(f"register {new_entry}")
        self.connections.append(new_entry)

    async def unregister(self, websocket):
        print(f"unregister {websocket}")
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

    async def send(self, message_dictionary):
        print(f'starting to send "{message_dictionary}"')
        recipient_tokens = message_dictionary.get("recipient_tokens")
        valid_recipient_tokens = [
            recipient_token
            for recipient_token in recipient_tokens
            if recipient_token in self.get_connection_user_tokens()
        ]
        if not valid_recipient_tokens:
            print(
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
                    print(f"Do stuff with message: {message}")
                    message_dictionary = json.loads(message)
                    if (
                        message_dictionary.get("type") == "authentication"
                    ) and message_dictionary.get("user_token"):
                        await self.register(
                            message_dictionary.get("user_token"), websocket
                        )
                    else:
                        await self.send(message_dictionary)
                except:
                    print(f"message {message} caused an error")
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
        print(f"adding to queue {message_dictionary}")
        self.q.put(json.dumps(full_dict))

    async def _send_message_to_server(self, message, websocket, expected_answers=0):
        answers = []
        print(f"_send_message_to_server {message}")
        await websocket.send(message)
        for i in range(expected_answers):
            answer = await websocket.recv()
            answers.append(answer)
            print(f"Client: Answer {i} from server: {answer}")
        return answers

    async def forever_function(self):
        async with websockets.connect(f"ws://{self.domain}:{self.port}") as websocket:
            print("Client: connected")
            while not self.quit:  #  this is an endless loop waiting for new queue items
                item = self.q.get()
                await self._send_message_to_server(item, websocket)
                self.q.task_done()

    def finally_at_stop(self):
        self.q.join()  # block until all tasks are done


ws = WebsocketsServer()
ws.start()


client = WebsocketsClient()
client.start()


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
