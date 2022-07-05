import logging
from queue import Queue

logger = logging.getLogger(__name__)


import asyncio
import time
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
        self.connected_websockets = set()

    async def register(self, websocket):
        print(f"register {websocket}")
        self.connected_websockets.add(websocket)

    async def unregister(self, websocket):
        print(f"unregister {websocket}")
        self.connected_websockets.remove(websocket)

    async def send_messages_to_all_connected_websockets(
        self, message, connected_websockets=None, exclude_websockets=None
    ):
        if connected_websockets is None:
            connected_websockets = self.connected_websockets
        connected_websockets = set(connected_websockets)
        for ws in exclude_websockets:
            connected_websockets.remove(ws)

        if connected_websockets:
            await asyncio.wait(
                [
                    connection.send(f"Server broadcasts: {message}")
                    for connection in list(connected_websockets)
                ]
            )
            return f"Successfully sent {message} to {connected_websockets}"
        else:
            return f'connected_websockets is empty. Nowhere to send "{message}"'

    async def _forever_listener(self, websocket, path):  # don't remove path
        await self.register(websocket)
        try:
            async for message in websocket:  # this is an endless loop waiting for incoming websocket messages
                print(f"Do sync stuff with message: {message}")
                msg = await self.send_messages_to_all_connected_websockets(
                    message, exclude_websockets={websocket}
                )
                await websocket.send(msg)
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

    def send(self, message):
        self.q.put(message)

    async def _send_message_to_server(self, message, websocket, expected_answers=1):
        answers = []
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
    client.send(f"loop {i}")

client.quit = True
time.sleep(2)
ws.quit = True
