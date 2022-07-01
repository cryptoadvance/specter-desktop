# Third-Party Service Integrations

A developer's guide for the Specter Desktop `Extension` framework. 

We currently rework the naming of extensions/plugins/services. If not otherwise stated, you can see those three terms as the same, for now.


## Concept
As much as possible, each `Service` implementation should be entirely self-contained with little or no custom code altering existing/core Specter functionality. There is a name for that: Extension-/Pluginframework.
The term `extension` will be used for all sorts extensions whereas `plugin` will be used as a component which can be de-/activated by a user.

All extensions are completely sperated in a specific folder-structure. There are internal extensions which `SHOULD` be located in `cryptoadvance.specterext.id_of_extension` but at least 2 extensions are still at the deprecated location of `cryptoadvance.specter.services`. However that does not mean that an extension needs to be located in the same repository than specter itself. There can and will be extensions which are located in their own repositories.

Independent whether an extension is shipped with the official specter-release-binaries and whether it's an internal (which is shipped) or external extension (which might be shipped), the creation of extensions is already heavily supported and encouraged.
Whether an extension is shipped with the official binary is entirely the choice of the Specter Team. However, you can simply develop extensions and use them on production (only for technical personel) as described in `specterext-dummy` (see below).

A description of how to create your own extension can be found at the [dummy-extension](https://github.com/cryptoadvance/specterext-dummy/). You will need to choose an organisation or username if you create one. This is used for package-structure.

All the attributes of an extension are currently (json-support is planned sooner or later) defined as attributes of a class which is derived from the class `Service` (should be renamed). That class has attributes which are essential. So let's discuss them briefly.

## Extension Attributes
Here is an Example. This class definition MUST be stored in a file called "service.py" within a package with the name `org-id.specterext.extions-id`.
```
class DiceService(Service):
    id = "dice"
    name = "Specter Dice"
    icon = "dice/dice_logo.png"
    logo = "dice/dice_logo.png"
    desc = "Send your bet!"
    has_blueprint = True
    blueprint_module = "k9ert.specterext.dice.controller"
    isolated_client = False
    devstatus = devstatus_alpha
```
So this defines the base `Service` class (to be renamed to "Extension") that all extensions must inherit from. This is wired to enable `Extension` auto-discovery. Any feature that is common to most or all `Service` integrations should be implemented here.
With inheriting from `Service` you get some usefull methods explained later.


The `id` needs to be unique within a specific specter-instance where this extension is part of. The `name` is the displayname as shown to the user in the plugin-area (currently there is not yet a technical difference between extensions and plugins). The `icon` will be used where labels are used to be diplayed if this extension is reserving addresses. The `logo` and the `desc` (ription) is also used in the plugin-area ("choose plugins").
If the extension has a UI (currently all of them have one), `has_blueprint` is True. `The blueprint_module` is referencing the controller-module where endpoints are defined. It's recommended to follow the format `org.specterext.extions-id.controller`.
`isolated_client` Should not be used yet. It is determining where in the url-path-tree the blueprint will be mounted. This might have an impact on whether the extension's frontend-client has access to the cookie used in specter. Check `config.py` for details.
`devstatus` is one of `devstatus_alpha`, `devstatus_beta` or `devstatus_prod` defined in `cryptoadvance.specter.services.service`. Each specter-instance will have a config-variable  called `SERVICES_DEVSTATUS_THRESHOLD` (prod in Production and alpha in Development) and depending on that, the plugin will be available to the user.

## Frontend aspects

As stated, you can have your own frontend with a blueprint. If you only have one, it needs to have a `/` route in order to be linkable from the `choose your plugin` page. 
If you create your extension with a blueprint, it'll create also a controller for you which, simplified, look like this:
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
 But you can also have more than one blueprint. Define them like this in your service-class:
```
    blueprint_modules = { 
        "default" : "mynym.specterext.rubberduck.controller",
        "ui" : "mynym.specterext.rubberduck.controller_ui"
    }
```
You have to have a default-blueprint which has the above mentioned index-page.
In your controller, the endpoint needs to be specified like this:
```
ui = RubberduckService.blueprints["ui"]
```


## Data-Storage
Effort has been taken to provide `Service` data storage that is separate from existing data stores in order to keep those areas clean and simple. Where touchpoints are unavoidable, they are kept to the absolute bare minimum (e.g. `User.services` list, `Address.service_id` field).


## `Address`-Level Integration
An `Address` can be associated with a `Service` (e.g. addr X received a smash buy from `Service` Foo) via the `Address.service_id` field.

A `Service` can also "reserve" and `Address` for future use by setting `Address.service_id`. The normal "Receive" UI will automatically skip any reserved `Address`es when generating a new receive addr. The reserved addresses are interleaved with ready-to-use addresses so that we don't create any potentially confusing wallet gaps (e.g. addrs 4, 6, and 8 are reserved but addrs 3, 5, and 7 are available).

Users can also manually associate an existing `Address` with a `Service` (this is useful when the user has info that the particular `Service` api can't provide for whatever reason).

_Note: TODO: manually un-reserve an `Address` from a `Service`._


### Service Configuration
In order to separate the service-configuration from the main-configuration, you can specify your config in a file called `config.py`. It's structure is similiar to the specter-wide `config.py`, e.g.:
```
class BaseConfig():
    SWAN_API_URL="https://dev-api.swanbitcoin.com"

class ProductionConfig(BaseConfig):
    SWAN_API_URL="https://api.swanbitcoin.com"
```
In your code, you can access the correct value as in any other flask-code, like `api_url = app.config.get("SWAN_API_URL")`. If the instance is running a config (e.g. `DevelopmentConfig`) which is not available in your service-specific config (as above), the inheritance-hirarchy from the mainconfig will get traversed and the first hit will get get configured. In this example, it would be `BaseConfig`.

### ServiceEncryptedStorage
Most `Service`s will require user secrets (e.g. API key and secret). Each Specter `User` will have their own on-disk encrypted `ServiceEncryptedStorage` with filename `<username>_services.json`. Note that the user's secrets for all `Service`s will be stored in this one file.

This is built upon the `GenericDataManager` class which supports optional encrypted fields. In this case all fields are encrypted. The `GenericDataManager` encryption can only be unlocked by each `User`'s individual `user_secret` that itself is stored encrypted on-disk; it is decrypted to memory when the `User` logs in.

For this reason `Service`s cannot be activated unless the user is signing in with a password-protected account (the default no-password `admin` account will not work).

_Note: during development if the Flask server is restarted or auto-reloads, the user's decrypted `user_secret` will no longer be in memory. The Flask context will still consider the user logged in after restart, but code that relies on having access to the `ServiceEncryptedStorage` will throw an error and/or prompt the user to log in again._

It is up to each `Service` implementation to decide what data is stored; the `ServiceEncryptedStorage` simply takes arbitrary json in and delivers it back out.

This is also where `Service`-wide configuration or other information should be stored, _**even if it is not secret**_ (see above intro about not polluting other existing data stores).

### ServiceEncryptedStorageManager
Because the `ServiceEncryptedStorage` is specific to each individual user, this manager provides convenient access to automatically retrieve the `current_user` from the Flask context and provide the correct user's `ServiceEncryptedStorage`. It is implemented as a `Singleton` which can be retrieved simply by importing the class and calling `get_instance()`.

This simplifies code to just asking for:
```
from .service_encrypted_storage import ServiceEncryptedStorageManager

ServiceEncryptedStorageManager.get_instance().get_current_user_service_data(service_id=some_service_id)
```

As a further convenience, the `Service` base class itself encapsulates `Service`-aware access to this per-`User` encrypted storage:
```
@classmethod
def get_current_user_service_data(cls) -> dict:
    return ServiceEncryptedStorageManager.get_instance().get_current_user_service_data(service_id=cls.id)
```

Whenever possible, external code should not directly access these `Service`-related support classes but rather should ask for them through the `Service` class.

### `ServiceUnencryptedStorage`
A disadvantage of the `ServiceEncryptedStorage` is, that the user needs to be freshly logged in in order to be able to decrypt the secrets. If you want to avoid that login but your extension should still store data on disk, you can use the `ServiceUnencryptedStorage`.

In parallel with the `ServiceEncryptedStorageManager` there is also a `ServiceUnencryptedStorageManager` which is used exactly the same way.

### `ServiceAnnotationsStorage`
Annotations are any address-specific or transaction-specific data from a `Service` that we might want to present to the user (not yet implemented). Example: a `Service` that integrates with a onchain storefront would have product/order data associated with a utxo. That additional data could be imported by the `Service` and stored as an annotation. This annotation data could then be displayed to the user when viewing the details for that particular address or tx.

Annotations are stored on a per-wallet and per-`Service` basis as _unencrypted_ on-disk data (filename: `<wallet_alias>_<service>.json`).

_Note: current `Service` implementations have not yet needed this feature so displaying annotations is not yet implemented._

## Data Storage Class Diagram

Unfortunately, the two unencrypted classes are derived from the encrypted one rather than having it the other way around or having abstract classes. This makes the diagram maybe a bit confusing.

[![](https://mermaid.ink/img/pako:eNqVVMFuwjAM_ZUqJzaVw66IIU0D7bRd0G6VItO4LFvqoCRlqhj_PpeWASLduhyiqH7v-dlOsxO5VSgmIjfg_VzD2kGZUcKr3Z-Q0Ol8DgGegWCNLpl-jcfJEt1W57ig3NWbgGoZrONoS-oJXjBfCaPcPxI-ENkAQVvyF7RHS4VeVw5WBpea1gaDpZbZZ6eT_9VyzMK18_8oZeIuE8l4fMsn4tOQRvZm7FPra24XZgLjK4--38BFTe1-uCORAe3acLOk1KSDlCOPpkgTxSBZWKPQpUlniUcnP7C-f7GENycmQYnSFvLdc7zQBk-hn1r4OxrlTxFjQY3ORKSHbUfcn3vuqTFm_MIyt4h3pX1zraTCA_0sX0b9ya5varxPB7DUKk0-wfC1HSh_PeJdFB7_Mc6sTKf--Hk2G96769lHhJrlW7xc1bJp538qGpQjJnVqhUhFia4ErfiROwhlIrxhiZmY8FFhAZUJmciogVYbHj8ulOb8YlKA8ZgKqIJd1pSLSXAVHkHdW9mh9t9YNMxZ)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNqVVMFuwjAM_ZUqJzaVw66IIU0D7bRd0G6VItO4LFvqoCRlqhj_PpeWASLduhyiqH7v-dlOsxO5VSgmIjfg_VzD2kGZUcKr3Z-Q0Ol8DgGegWCNLpl-jcfJEt1W57ig3NWbgGoZrONoS-oJXjBfCaPcPxI-ENkAQVvyF7RHS4VeVw5WBpea1gaDpZbZZ6eT_9VyzMK18_8oZeIuE8l4fMsn4tOQRvZm7FPra24XZgLjK4--38BFTe1-uCORAe3acLOk1KSDlCOPpkgTxSBZWKPQpUlniUcnP7C-f7GENycmQYnSFvLdc7zQBk-hn1r4OxrlTxFjQY3ORKSHbUfcn3vuqTFm_MIyt4h3pX1zraTCA_0sX0b9ya5varxPB7DUKk0-wfC1HSh_PeJdFB7_Mc6sTKf--Hk2G96769lHhJrlW7xc1bJp538qGpQjJnVqhUhFia4ErfiROwhlIrxhiZmY8FFhAZUJmciogVYbHj8ulOb8YlKA8ZgKqIJd1pSLSXAVHkHdW9mh9t9YNMxZ)

### callback methods
Your service-class will inherit a callback-method which will get called for various reasons with the "reason" being a string as the first parameter. Checkout the `cryptoadvance.specter.services.callbacks` file for the specific callbacks.

Some important one is the `after_serverpy_init_app` which passes a `Scheduler` class which can be used to setup regular tasks.


### `controller.py`
The minimal url routes for `Service` selection and management.


## Implementation Class Structure
Child implementation classes (e.g. `SwanService`) should be self-contained within their own subdirectory in `services`. e.g.:
```
cryptoadvance.specter.services.swan
```

Each implementation must have the following required components:
```
/static/<service_id>
/templates/<service_id>
controller.py
service.py
```

This makes each implementation its own Flask `Blueprint`.

### `/static`
Because of Flask `Blueprint` imports, you can just add static files here and reference them (e.g. "static/<service_id>/img/blah.png") as if they were in the main `/static` files root dir.

### `/templates/<service_id>`
Again, Flask `Blueprint`s import the `/templates` directory as-is, but to avoid namespace collisions on the template files (e.g. `/templates/index.html`) they should be contained within a subdirectory named with the `Service.id` (e.g. `/templates/swan/index.html`)

### `Service` Implementation Class
Must inherit from `Service` and provide any additional functionality needed. The `Service` implementation class is meant to be the main hub for all things related to that particular `Service`. In general, external code would ideally only interact with the `Service` implementation class (e.g. )

### `controller.py`
Flask `Blueprint` for any endpoints required by this `Service`.

The coding philosophy should be to keep this code as simple as possible and keep most or all of the actual logic in the `Service` implementation class.

### Additional Files
The `SwanService` also includes an `api.py` to separate its back-end API calls from the user-facing `controller.py` endpoints. In general this is recommended to provide a clear separation.

An individual `Service` implementation may add whatever additional files or classes it needs.

