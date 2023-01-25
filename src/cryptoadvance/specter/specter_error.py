import logging
from .util.shell import get_last_lines_from_file
from flask import current_app as app

logger = logging.getLogger(__name__)


class SpecterError(Exception):
    """A SpecterError contains meaningfull messages which can be passed directly to the user"""

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(SpecterError, self).__init__(message)
        # potentially, we could add own stuff now here:


class SpecterInternalException(Exception):
    pass


class BrokenCoreConnectionException(SpecterInternalException):
    pass


class ExtProcTimeoutException(SpecterInternalException):
    """A Exception which is thrown because an external process timed out
    use check_logfile to get some lines in loglines
    probably improvable for processes which don't have a logfile
    """

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(ExtProcTimeoutException, self).__init__(message)

    def check_logfile(self, logfile_location):
        try:
            self.logfile_location = logfile_location
            self.loglines = "     ".join(get_last_lines_from_file(logfile_location))
        except IOError as ioe:
            self.message = str(self) + f" ({ioe})"
            self.loglines = ""

    def get_logger_friendly(self):
        return f"""----------- {self.logfile_location} -----------
        {self.loglines}
        ------------------------------------------------------"""


def handle_exception(exception, user=None):
    """prints the exception and most important the stacktrace"""
    try:
        if app.config["SPECTER_CONFIGURATION_CLASS_FULLNAME"].endswith(
            "DevelopmentConfig"
        ):
            raise exception
    except RuntimeError:  # Application context might be missing
        pass
    logger.error("Unexpected error:")
    logger.error(
        "----START-TRACEBACK-----------------------------------------------------------------"
    )
    logger.exception(exception)  # the exception instance
    logger.error(
        "----END---TRACEBACK-----------------------------------------------------------------"
    )
