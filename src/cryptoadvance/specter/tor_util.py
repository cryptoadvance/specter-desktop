import os
from stem.control import Controller
from .server import DATA_FOLDER


def run_on_hidden_service(
    app, tor_port=80, save_address_to=None, **kwargs
):
    port = 5000  # default flask port
    if 'port' in kwargs:
        port = kwargs['port']
    else:
        kwargs['port'] = port

    with Controller.from_port() as controller:
        print(' * Connecting to tor')
        controller.authenticate()
        app.controller = controller
        app.port = port
        app.tor_port = tor_port
        app.save_tor_address_to = save_address_to

        start_hidden_service(app)
        try:
            app.run(**kwargs)
        finally:
            stop_hidden_services(app)


def start_hidden_service(app):
    key_path = os.path.abspath(
        os.path.expanduser(os.path.join(DATA_FOLDER, '.tor_service_key'))
    )
    app.tor_service_id = None

    if not os.path.exists(key_path):
        service = app.controller.create_ephemeral_hidden_service(
            {app.tor_port: app.port}, await_publication=True
        )
        app.tor_service_id = service.service_id
        print(
            '* Started a new hidden service with the address of %s.onion'
            % app.tor_service_id
        )

        with open(key_path, 'w') as key_file:
            key_file.write(
                '%s:%s' % (service.private_key_type, service.private_key)
            )
    else:
        with open(key_path) as key_file:
            key_type, key_content = key_file.read().split(':', 1)

        service = app.controller.create_ephemeral_hidden_service(
            {app.tor_port: app.port},
            key_type=key_type,
            key_content=key_content,
            await_publication=True,
        )
        app.tor_service_id = service.service_id
        print('* Resumed %s.onion' % app.tor_service_id)

    # save address to file
    if app.save_tor_address_to is not None:
        with open(app.save_tor_address_to, 'w') as f:
            f.write('%s.onion' % app.tor_service_id)
    app.tor_service_id = app.tor_service_id


def stop_hidden_services(app):
    hidden_services = app.controller.list_ephemeral_hidden_services()
    print(' * Shutting down our hidden service')
    for tor_service_id in hidden_services:
        app.controller.remove_ephemeral_hidden_service(tor_service_id)
    # Sanity
    if (len(app.controller.list_ephemeral_hidden_services()) != 0):
        print(' * Failed to shut down our hidden services...')
    else:
        print(' * Hidden services were shut down successfully')
        app.tor_service_id = None
