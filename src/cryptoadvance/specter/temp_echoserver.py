from flask import Flask, render_template, request
import simple_websocket
import threading

app = Flask(__name__)


connections = []


@app.route("/echo", websocket=True)
def echo():
    ws = simple_websocket.Server(request.environ)
    print(f"Sfarting server {ws}")
    connections.append(ws)
    print(f"There are {len(connections)} connections registered")
    try:
        handle(ws)
    except simple_websocket.ConnectionClosed:
        print(f"Closed Connection")

    print(f"Unregister connection {ws}")
    connections.pop(connections.index(ws))


def handle(ws):
    while True:
        print(f"Waiting on {ws} for incoming data")
        data = ws.receive()
        print(f"{ws} recieved {data}")
        send_to_all_connections(data)


def send_to_all_connections(data):
    def target():
        try:
            print(f"Sending {data} to {ws}")
            ws.send(data)
        except simple_websocket.ConnectionClosed:
            print(f"Closed Connection")
            print(f"Unregister connection {ws}")
            connections.pop(connections.index(ws))

    threads = []
    for ws in connections:
        thread = threading.Thread(target=target)
        thread.daemon = True  # die when the main thread dies
        thread.start()
        thread.join()


@app.route("/")
def main():
    return ""


from pathlib import Path

if __name__ == "__main__":

    app.run(
        ssl_context=(
            f"{Path.home()}/.specter_dev/cert.pem",
            f"{Path.home()}/.specter_dev/key.pem",
        )
    )


# Do this in the console after running the server
# var websocket = new WebSocket(`wss://127.0.0.1:5000/echo`)
# websocket.onmessage = function(message) {
#             console.log(message)
#         };

# websocket.send('dd2d')
