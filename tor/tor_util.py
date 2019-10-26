import os
import stem
from stem.control import Controller

from dotenv import load_dotenv
load_dotenv()   # Load the secrets from .env


def run_on_hidden_service(app, port, debug, extra_files):
    with Controller.from_port() as controller:
        print(' * Connecting to tor')
        controller.authenticate(os.getenv('TOR_PASSWORD'))

        key_path = os.path.expanduser('.tor_service_key')
        tor_service_id = None

        if not os.path.exists(key_path):
            service = controller.create_ephemeral_hidden_service({80: port}, await_publication = True)
            tor_service_id = service.service_id
            print("Started a new hidden service with the address of %s.onion" % tor_service_id)

            with open(key_path, 'w') as key_file:
                key_file.write('%s:%s' % (service.private_key_type, service.private_key))
        else:
            with open(key_path) as key_file:
                key_type, key_content = key_file.read().split(':', 1)

            service = controller.create_ephemeral_hidden_service({80: port}, key_type = key_type, key_content = key_content, await_publication = True)
            tor_service_id = service.service_id
            print("Resumed %s.onion" % tor_service_id)

        try:
            app.run(port=port, debug=debug, extra_files=extra_files)
        finally:
            if tor_service_id:
                print(" * Shutting down our hidden service")
                controller.remove_ephemeral_hidden_service(tor_service_id)
