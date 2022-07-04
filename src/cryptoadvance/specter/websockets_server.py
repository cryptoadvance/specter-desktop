import os
import logging

logger = logging.getLogger(__name__)


import asyncio
import os
import time
import websockets
import threading


class WebsocketsServer:
    def __init__(self):
        self.domain = "localhost"
        self.port = "5051"
        self.connections = set()

    async def register(self, websocket):
        print(f"register {websocket}")
        self.connections.add(websocket)

    async def unregister(self, websocket):
        print(f"unregister {websocket}")
        self.connections.remove(websocket)

    async def send_messages_to_all(self, message, websocket):
        if self.connections:
            print(f"Sending messages to all {self.connections}")
            await asyncio.wait(
                [
                    connection.send(f"Server answers {message}")
                    for connection in list(self.connections)
                ]
            )
        else:
            logger.warning(f'connection_list is empty. Nowhere to send "{message}".')

    async def handler(self, websocket, path):  # don't remove path
        await self.register(websocket)
        try:
            await websocket.send("Connected")
            async for message in websocket:  # this is an endless loop waiting for incoming websocket messages
                print(f"Do sync stuff with message: {message}")
                await self.send_messages_to_all(message, websocket)
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

    def start_server_thread(self, in_new_thread=True):
        if in_new_thread:
            t = threading.Thread(target=self.start_forever_websockets_server)
            t.start()
        else:
            self.start_forever_websockets_server()


class WebsocketsClient:
    def __init__(self):
        self.domain = "localhost"
        self.port = "5051"

    async def send_message(self, message, expected_answers=2):
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
ws.start_server_thread()


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
