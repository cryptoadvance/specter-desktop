import logging
from flask import Flask, Response, redirect, render_template, request, url_for, flash
from flask_login import login_required

from cryptoadvance.specter.services.service_apikey_storage import (
    ServiceApiKeyStorageError,
)
from ..service_settings_manager import ServiceSettingsManager
from .manifest import DummyService2


"""
    Empty placeholder just so the dummyservice/static folder can be wired up to retrieve its icon.
"""

logger = logging.getLogger(__name__)

dummyservice2_endpoint = DummyService2.blueprint

