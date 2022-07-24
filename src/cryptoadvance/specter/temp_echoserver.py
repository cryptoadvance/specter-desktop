from flask import Flask, render_template, request
import simple_websocket

app = Flask(__name__)


@app.route("/echo", websocket=True)
def echo():
    ws = simple_websocket.Server(request.environ)
    print(f"Sfarting server {ws}")
    try:
        while True:
            data = ws.receive()
            print(data)
            ws.send(data)
    except simple_websocket.ConnectionClosed:
        pass
    return ""


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
