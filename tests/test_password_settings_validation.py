from importlib import import_module


def test_empty_password_does_not_enable_password_only(app_no_node, monkeypatch):
    settings = import_module("cryptoadvance.specter.server_endpoints.settings")
    specter = app_no_node.specter
    original_method = specter.config["auth"]["method"]
    admin = specter.user_manager.admin
    original_hash = admin.password_hash
    monkeypatch.setattr(settings, "notify_upgrade", lambda *args: None)
    monkeypatch.setattr(settings, "render_template", lambda *args, **kwargs: "invalid")

    with app_no_node.test_request_context(
        "/settings/auth",
        method="POST",
        data={
            "action": "save",
            "method": "passwordonly",
            "rate_limit": "0",
            "registration_link_timeout": "0",
            "specter_password_only": "",
        },
    ):
        app_no_node.login("admin")
        assert settings.auth() == "invalid"

    assert specter.config["auth"]["method"] == original_method
    assert admin.password_hash is original_hash
    assert specter.user_manager.admin.password_hash == original_hash
