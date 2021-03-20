import logging

logger = logging.getLogger(__name__)


class SpecterError(Exception):
    """ A SpecterError contains meaningfull messages which can be passed directly to the user """

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(SpecterError, self).__init__(message)
        # potentially, we could add own stuff now here:


def handle_exception(exception, user=None):
    """ prints the exception and most important the stacktrace """
    logger.error("Unexpected error:")
    logger.error(
        "----START-TRACEBACK-----------------------------------------------------------------"
    )
    logger.exception(exception)  # the exception instance
    logger.error(
        "----END---TRACEBACK-----------------------------------------------------------------"
    )
