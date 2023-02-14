# Frontend aspects

## controller.py

You can have your own frontend with a blueprint (flask blueprints are explained [here](https://realpython.com/flask-blueprint/)). If you only have one, it needs to have a `/` route in order to be linkable from the `choose your plugin` page. 
If you create your extension with a blueprint, it'll also create a controller for you which, simplified, looks like this:
```python
rubberduck_endpoint = ScratchpadService.blueprint

def ext() -> ScratchpadService:
    ''' convenience for getting the extension-object'''
    return app.specter.ext["rubberduck"]

def specter() -> Specter:
    ''' convenience for getting the specter-object'''
    return app.specter


@rubberduck.route("/")
@login_required
@user_secret_decrypted_required
def index():
    return render_template(
        "rubberduck/index.jinja",
    )
[...]
```

You can also have more than one blueprint. Define them like this in your service class:
```python
    blueprint_modules = { 
        "default" : "mynym.specterext.rubberduck.controller",
        "ui" : "mynym.specterext.rubberduck.controller_ui"
    }
```

You have to have a default blueprint which has the above mentioned index page.
In your controller, the endpoint needs to be specified like this:

```python
ui = RubberduckService.blueprints["ui"]
```

## Templates and static resources

The minimal url routes for `Service` selection and management. As usualy in Flask, `templates` and `static` resources are in their respective subfolders. Please note that there is an additional directory with the id of the extension which looks redundant at first. This is due to the way blueprints are loading templates and ensures that there are no naming collisions. Maybe at a later stage, this can be used to let plugins override other plugin's templates.

## Modifying non-extension pages

You might have an extension which wants to inject e.g. JavaScript code into each and every page of Specter Desktop. You can do that via overwriting one of the `inject_in_basejinja_*` methods in your service-class:
```python
    @classmethod
    def inject_in_basejinja_head(cls):
        ''' e.g. rendering some snippet '''
        return render_template("devhelp/html_inject_in_basejinja_head.jinja")

    @classmethod
    def inject_in_basejinja_body_top(cls):
        ''' or directly returning text '''
        return "<script>console.log('Hello from body top')"

    @classmethod
    def inject_in_basejinja_body_bottom(cls):
        return "something here"
```

For this to work, the extension needs to be activated for the user, though.

## Extending dialogs
You can extend the settings dialog or the wallet dialog with your own templates. To do that, create a callback method in your service like:

```python
from cryptoadvance.specter.services import callbacks
# [...]
    def callback_add_settingstabs(self):
        ''' Extending the settings tab with an own tab called "myexttitle" '''
        return [{"title": "myexttitle", "endpoint":"myext_something"}]

    def callback_add_wallettabs(self):
        ''' Extending the wallets tab with an own tab called "mywalletdetails" '''
        return [{"title": "mywalletdetails", "endpoint":"myext_mywalletdetails"}]
```

In this case, this would add a tab called "myexttitle" and you're now supposed to provide an endpoint in your controller which might be called `myext_something` e.g. like this:

```python
@myext_endpoint.route("/settings_something", methods=["GET"])
def myext_something():
    return render_template(
        "myext/some_settingspage.jinja",
        ext_settingstabs = app.specter.service_manager.execute_ext_callbacks(
            callbacks.add_settingstabs
        )
    )
```

If you want to have an additional wallet tab, you would specify something like:

```python
@myext_endpoint.route("/wallet/<wallet_alias>/mywalletdetails", methods=["GET"])
def myext_mywalletdetails(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    return render_template(
        "myext/mywalletdetails.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        ext_wallettabs = app.specter.service_manager.execute_ext_callbacks(
            callbacks.add_wallettabs
        )
    )
```

The `some_settingspage.jinja` should probably look exactly like all the other setting pages and you would do this like this:

```jinja
{% extends "base.jinja" %}
{% block main %}
	<form action="?" method="POST" onsubmit="showPacman()">
		<input type="hidden" class="csrf-token" name="csrf_token" value="{{ csrf_token() }}"/>
		<h1 id="title" class="settings-title">Settings</h1>
		{% from 'settings/components/settings_menu.jinja' import settings_menu %}
		{{ settings_menu('myext_something', current_user, ext_settingstabs) }}
		<div class="card" style="margin: 20px auto;">
			<h1>{{ _("Something something") }} </h1>
		</div>
	</form>
{% endblock %}
```

![](./images/extensions/add_settingstabs.png)


A reasonable `mywalletdetails.jinja` would look like this:

```jinja
{% extends "wallet/components/wallet_tab.jinja" %}
{% set tab = 'my details' %}
{% block content %}
	<br>
	<div class="center card" style="width: 610px; padding-top: 25px;">
        Some content here for the wallet {{ wallet_alias }}
	</div>
{% endblock %}
```

![](./images/extensions/add_wallettabs.png)

## Extending certain pages or complete endpoints (don't use this for now)

For some endpoints, there is the possibility to extend/change parts of a page or the complete page. This works by declaring the `callback_adjust_view_model` method in your extension and modify the ViewModel which got passed into the callback. As there is only one callback for all types of ViewModels, you will need to check for the type that you're expecting and only adjust this type. Here is an example:

```python
from cryptoadvance.specter.server_endpoints.welcome.welcome_vm import WelcomeVm

class ExtensionidService(Service):
    [...}
    def callback_adjust_view_model(self, view_model: WelcomeVm):
        if type(view_model) == WelcomeVm:
            # potentially, we could make a redirect here:
            # view_model.about_redirect=url_for("spectrum_endpoint.some_enpoint_here")
            # but we do it small here and only replace a specific component:
            view_model.get_started_include = "spectrum/welcome/components/get_started.jinja"
        return view_model
```
Make sure to return the view_model in anycase. No matter whether it's the correct type or not.

In this example, a certain part of the page gets replaced. As you can read in the comments, you could also trigger a complete redirect to a different endpoint.

Currently, only two `ViewModels` are existing. Check them out. Don't hesitate to create an issue if you'd like to modify something where no ViewModel exists yet:
- cryptoadvance.specter.server_endpoints.welcome.welcome_vm
- cryptoadvance.specter.server_endpoints.wallets.wallets_vm
