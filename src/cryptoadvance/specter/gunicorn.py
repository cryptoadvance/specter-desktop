import multiprocessing
from cryptoadvance.specter.server import init_app, create_app, create_and_init

import gunicorn.app.base


class SpecterGunicornApp(gunicorn.app.base.Application):
    def __init__(
        self, config="cryptoadvance.specter.config.ProductionConfig", options=None
    ):
        """
        i guess those are the potential options:
        usage: __main__.py [-h] [-v] [-c CONFIG] [-b ADDRESS] [--backlog INT] [-w INT] [-k STRING] [--threads INT]
               [--worker-connections INT] [--max-requests INT] [--max-requests-jitter INT] [-t INT] [--graceful-timeout INT]
               [--keep-alive INT] [--limit-request-line INT] [--limit-request-fields INT] [--limit-request-field_size INT]
               [--reload] [--reload-engine STRING] [--reload-extra-file FILES] [--spew] [--check-config] [--print-config]
               [--preload] [--no-sendfile] [--reuse-port] [--chdir CHDIR] [-D] [-e ENV] [-p FILE] [--worker-tmp-dir DIR]
               [-u USER] [-g GROUP] [-m INT] [--initgroups] [--forwarded-allow-ips STRING] [--access-logfile FILE]
               [--disable-redirect-access-to-syslog] [--access-logformat STRING] [--error-logfile FILE] [--log-level LEVEL]
               [--capture-output] [--logger-class STRING] [--log-config FILE] [--log-syslog-to SYSLOG_ADDR] [--log-syslog]
               [--log-syslog-prefix SYSLOG_PREFIX] [--log-syslog-facility SYSLOG_FACILITY] [-R] [--statsd-host STATSD_ADDR]
               [--dogstatsd-tags DOGSTATSD_TAGS] [--statsd-prefix STATSD_PREFIX] [-n STRING] [--pythonpath STRING]
               [--paste STRING] [--proxy-protocol] [--proxy-allow-from PROXY_ALLOW_IPS] [--keyfile FILE] [--certfile FILE]
               [--ssl-version SSL_VERSION] [--cert-reqs CERT_REQS] [--ca-certs FILE] [--suppress-ragged-eofs]
               [--do-handshake-on-connect] [--ciphers CIPHERS] [--paste-global CONF] [--strip-header-spaces]
        """
        self.options = options or {}
        self.config = config
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return create_and_init(self.config)
