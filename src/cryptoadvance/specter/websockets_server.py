import os
import logging

logger = logging.getLogger(__name__)


import asyncio
import os
import time
import websockets


domain = "localhost"
ws_port = "5051"


CONNECTIONS = set()


async def register(websocket):
    print(f"register {websocket}")
    CONNECTIONS.add(websocket)


async def unregister(websocket):
    CONNECTIONS.remove(websocket)


async def notify_users(message, websocket):
    connection_list = []
    for connection in CONNECTIONS:
        connection_list.append(connection)

    if connection_list:
        await asyncio.wait(
            [
                connection.send(f"Server answers {message}")
                for connection in connection_list
            ]
        )
    else:
        print(f'connection_list is empty. Nowhere to send "{message}".')


async def message_control(websocket, path):
    await register(websocket)
    try:
        await websocket.send("Connected")
        async for message in websocket:
            print(message)
            await notify_users(message, websocket)
    finally:
        await unregister(websocket)


print("\nStarting websocker server")
start_server = websockets.serve(message_control, domain, ws_port)

# this should make it also wiork in multithreading  https://stackoverflow.com/questions/58617631/python3-websocket-in-thread
try:
    event_loop = asyncio.get_event_loop()
except:
    event_loop = asyncio.new_event_loop()

event_loop.run_until_complete(start_server)
event_loop.run_forever()
