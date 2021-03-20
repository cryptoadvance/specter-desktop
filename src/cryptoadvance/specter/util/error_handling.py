import logging

logger = logging.getLogger(__name__)


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
