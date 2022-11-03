from dataclasses import dataclass


@dataclass
class WelcomeVm:
    """An object to control what is being displayed at the About endpoint
    If you set the different attributes, you can modify the behaviour.
    e.g. setting the about_redirect to url_for(...) will cause a redirect

    Check the welcome.jinja template to understand exact usage
    """

    about_redirect: str = None
    specter_remote_include: str = "welcome/components/specter_remote.jinja"
    get_started_include: str = "welcome/components/get_started.jinja"
    tick_checkboxes_include: str = "welcome/components/tick_checkboxes.jinja"
    remaining_remarks_include = "welcome/components/remaining_remarks.jinja"
