import logging
from queue import Queue

logger = logging.getLogger(__name__)


import asyncio
import time
import websockets
import threading


class WebsocketsServer:
    def __init__(self):
        self.domain = "localhost"
        self.port = "5051"
        self.connected_websockets = set()
        self.q = Queue()

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
            return "Successfully sent {message} to {connected_websockets}"
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
        finally:
            await self.unregister(websocket)

    def _forever_websockets_server(self):
        print("Starting websocker server")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ws_server = websockets.serve(self._forever_listener, self.domain, self.port)

        loop.run_until_complete(ws_server)
        loop.run_forever()  # this is missing
        loop.close()

    def start(self, in_new_thread=True):
        if in_new_thread:
            t = threading.Thread(target=self._forever_websockets_server)
            t.start()
        else:
            self._forever_websockets_server()


class WebsocketsClient:
    "keeps an open websocket connection"

    def __init__(self):
        self.domain = "localhost"
        self.port = "5051"
        self.q = Queue()

    def send(self, message):
        self.q.put(message)

    async def _send_message_to_server(self, message, websocket, expected_answers=1):
        answers = []
        print("Client: connected")
        await websocket.send(message)
        for i in range(expected_answers):
            answer = await websocket.recv()
            answers.append(answer)
            print(f"Client: Answer {i} from server: {answer}")
        return answers

    async def _forever_queue_worker(self):
        async with websockets.connect(f"ws://{self.domain}:{self.port}") as websocket:
            while True:  #  this is an endless loop waiting for new queue items
                item = self.q.get()
                await self._send_message_to_server(item, websocket)
                self.q.task_done()

    def _forever_websockets_client(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._forever_queue_worker())
        loop.close()

    def start(self, in_new_thread=True):
        try:
            if in_new_thread:
                t = threading.Thread(target=self._forever_websockets_client)
                t.start()
            else:
                self._forever_websockets_client()
        finally:
            self.q.join()  # block until all tasks are done


ws = WebsocketsServer()
ws.start()


client = WebsocketsClient()
client.start()


# get into the server loop via a queue

for i in range(1000):
    time.sleep(2)
    client.send(f"loop {i}")
