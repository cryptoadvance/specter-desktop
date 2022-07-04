import logging

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
                    connection.send(f"Server answers {message}")
                    for connection in list(connected_websockets)
                ]
            )
            return "Successfully sent {message} to {connected_websockets}"
        else:
            return f'connected_websockets is empty. Nowhere to send "{message}"'

    async def handler(self, websocket, path):  # don't remove path
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

    def start_forever_websockets_server(self):
        print("Starting websocker server")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ws_server = websockets.serve(self.handler, self.domain, self.port)

        loop.run_until_complete(ws_server)
        loop.run_forever()  # this is missing
        loop.close()

    def start(self, in_new_thread=True):
        if in_new_thread:
            t = threading.Thread(target=self.start_forever_websockets_server)
            t.start()
        else:
            self.start_forever_websockets_server()


class WebsocketsClient:
    def __init__(self):
        self.domain = "localhost"
        self.port = "5051"

    async def send_message(self, message, expected_answers=1):
        messages = []
        async with websockets.connect(f"ws://{self.domain}:{self.port}") as websocket:
            print("Client: connected")
            await websocket.send(message)
            for i in range(expected_answers):
                msg = await websocket.recv()
                messages.append(msg)
                print(f"Client: Answer {i} from server: {msg}")
        return messages


ws = WebsocketsServer()
ws.start()


client = WebsocketsClient()


async def f():
    return await client.send_message(f"Main thread: loop {i}")


for i in range(1000):
    print(
        f"Loop {i} --------------------------------------------------------------------------"
    )
    time.sleep(2)
    messages = asyncio.get_event_loop().run_until_complete(f())
    print(messages)
