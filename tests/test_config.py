""" testing the config.py """

from flask import Config


def test_config():
    " how can you read the config if do not create an app? " ""
    config = Config(".")
    print(config)
    config.from_object("cryptoadvance.specter.config.DevelopmentConfig")
    print(config)
    assert config["PORT"] == 25441
