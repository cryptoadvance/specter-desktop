import simple_websocket, ssl
from pathlib import Path


def main():

    ssl_paths = (
        f"{Path.home()}/.specter_dev/cert.pem",
        f"{Path.home()}/.specter_dev/key.pem",
    )

    ssl_context = ssl._create_unverified_context(ssl.PROTOCOL_TLS_CLIENT)
    # see https://pythontic.com/ssl/sslcontext/load_cert_chain
    ssl_context.load_cert_chain(certfile=ssl_paths[0], keyfile=ssl_paths[1])

    ws = simple_websocket.Client("wss://localhost:5000/echo", ssl_context=ssl_context)
    try:
        while True:
            data = input("> ")
            ws.send(data)
            data = ws.receive()
            print(f"< {data}")
    except (KeyboardInterrupt, EOFError, simple_websocket.ConnectionClosed):
        ws.close()


if __name__ == "__main__":
    main()
