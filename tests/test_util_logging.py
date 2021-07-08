import logging
from cryptoadvance.specter.util.logging import DuplicateFilter


def test_DuplicateFilter(caplog):
    caplog.set_level(logging.DEBUG)

    df = DuplicateFilter()

    clogger = logging.getLogger("cryptoadvance")
    clogger.setLevel(logging.DEBUG)

    # for handler in logging.root.handlers:
    #    print(handler)
    logging.root.handlers[3].addFilter(
        df
    )  # seems we have to configure at a specific handler

    logger = logging.getLogger("cryptoadvance.specter.some.package")
    logger.info("hi!")
    for i in range(0, 20):
        logger.info(" i said hi!")
    logger.info("Muh")

    assert caplog.text.count("hi!") == 1
    assert caplog.text.count(" i said hi!") == 1
