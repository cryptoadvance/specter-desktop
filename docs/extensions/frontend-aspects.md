# Frontend aspects

## controller.py

You can have your own frontend with a blueprint (flask blueprints are explained [here](https://realpython.com/flask-blueprint/)). If you only have one, it needs to have a `/` route in order to be linkable from the `choose your plugin` page. 
If you create your extension with a blueprint, it'll also create a controller for you which, simplified, looks like this:
```
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
```
    blueprint_modules = { 
        "default" : "mynym.specterext.rubberduck.controller",
        "ui" : "mynym.specterext.rubberduck.controller_ui"
    }
```

You have to have a default blueprint which has the above mentioned index page.
In your controller, the endpoint needs to be specified like this:

```
ui = RubberduckService.blueprints["ui"]
```

## Templates and Static Resources

The minimal url routes for `Service` selection and management. As usualy in Flask, `templates` and `static` resources are in their respective subfolders. Please note that there is an additional directory with the id of the extension which looks redundant at first. This is due to the way blueprints are loading templates and ensures that there are no naming collisions. Maybe at a later stage, this can be used to let plugins override other plugin's templates.

## Modifying non-extension pages

You might have an extension which wants to inject e.g. javascript code into each and every page of specter-desktop. You can do that via overwriting one of the `inject_in_basejinja_*` methods in your service-class:
```
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