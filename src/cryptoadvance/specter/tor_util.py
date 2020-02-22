import os
import stem
from stem.control import Controller
from .server import DATA_FOLDER

def run_on_hidden_service(app, tor_password=None, tor_port=80, save_address_to=None, **kwargs):
    port = 5000 # default flask port
    if "port" in kwargs:
        port = kwargs["port"]
    else:
        kwargs["port"] = port

    with Controller.from_port() as controller:
        print(' * Connecting to tor')
        controller.authenticate(tor_password)

        key_path = os.path.abspath(os.path.expanduser(os.path.join(DATA_FOLDER,'.tor_service_key')))
        tor_service_id = None

        if not os.path.exists(key_path):
            service = controller.create_ephemeral_hidden_service({tor_port: port}, await_publication = True)
            tor_service_id = service.service_id
            print("* Started a new hidden service with the address of %s.onion" % tor_service_id)

            with open(key_path, 'w') as key_file:
                key_file.write('%s:%s' % (service.private_key_type, service.private_key))
        else:
            with open(key_path) as key_file:
                key_type, key_content = key_file.read().split(':', 1)

            service = controller.create_ephemeral_hidden_service({tor_port: port}, key_type = key_type, key_content = key_content, await_publication = True)
            tor_service_id = service.service_id
            print("* Resumed %s.onion" % tor_service_id)

        # save address to file
        if save_address_to is not None:
            with open(save_address_to, "w") as f:
                f.write("%s.onion" % tor_service_id)

        try:
            app.run(**kwargs)
        finally:
            if tor_service_id:
                print(" * Shutting down our hidden service")
                controller.remove_ephemeral_hidden_service(tor_service_id)
