"""
Test to verify that livereload.js is only included in DevelopmentConfig
"""
import logging
import pytest
from cryptoadvance.specter.server import create_app, init_app
from cryptoadvance.specter.specter import Specter


def test_livereload_not_in_testconfig(caplog, app_no_node):
    """
    Test that livereload.js is NOT included when using TestConfig (similar to ProductionConfig)
    The app_no_node fixture uses TestConfig which should NOT include livereload.js
    """
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    
    client = app_no_node.test_client()
    
    # Get the welcome page (which uses base.jinja)
    result = client.get("/", follow_redirects=True)
    assert result.status_code == 200
    
    # Verify that livereload.js script is NOT in the response
    response_text = result.data.decode('utf-8')
    assert '35729/livereload.js' not in response_text, \
        "livereload.js should NOT be included in TestConfig (similar to ProductionConfig)"


def test_livereload_in_developmentconfig(empty_data_folder):
    """
    Test that livereload.js IS included when using DevelopmentConfig
    """
    # Create app with DevelopmentConfig and minimal specter instance
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)
    app = create_app(config='DevelopmentConfig')
    app.config["TESTING"] = True
    app.testing = True
    app.tor_service_id = None
    app.tor_enabled = False
    
    with app.app_context():
        init_app(app, specter=specter)
        client = app.test_client()
        
        # Get the welcome page (which uses base.jinja)
        result = client.get("/", follow_redirects=True)
        assert result.status_code == 200
        
        # Verify that livereload.js script IS in the response
        response_text = result.data.decode('utf-8')
        assert '35729/livereload.js' in response_text, \
            "livereload.js SHOULD be included in DevelopmentConfig"
