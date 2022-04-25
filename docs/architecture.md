# Architectural Notes

specter-desktop and specter-cloud are flask-applications and follow typical Model-View-Control-principles. The model-part is covered by a number of business-objects and managers who are responsible for maintaining/managing those. Currently we have these managers:

## Managers

* GenericDataManager is abstracting persistence-aspects and most managers which are persisting json-data are derived from this one.
* ConfigManager where the api-docs tells us: "The ConfigManager manages the configuration persisted in config.json. It's not supposed to have any side-effects. Setting and getting only with a lot of validation and computing while setting/getting."
* DeviceManager where the api-docs tells us: "A DeviceManager mainly manages the persistence of a device-json-structures compliant to helper.load_jsons.py".
* NodeManager manages internal and external nodes.
* UserManager manages all stuff regarding Users.
* Similarly the WalletManager
        
## Views / Blueprints
The controller is covered by "server_endpoints". Those are split up in “blueprints”. This is a way to split the urls in sub-urls. These sub-urls are loosely related to the business-objects: `/welcome`, `/auth`, `/devices`, `/nodes`, `/price`, `/services` (should be renamed "`/plugins`"), `/settings`, `/setup`, `/wallets`.

## Views
The views are effectively jinja2 templates which can extend from higher order ones and have placeholders which templates can then override. The `base.jinja` lays out the basic layout having a block for the `sidebar` and a `main` block (plus `head` and `scripts` ). Some blueprints (`/settings`,`/wallets`) span up a top-level-navigation. In that case, the template extend from its specific blueprint-base-template which in turn provides a block called `content` and the template decides which menu-point is active:
```
{% extends "wallet/components/wallet_tab.jinja" %}
{% set tab = 'receive' %}
{% block content %}
...
```
This is also a pattern used for plugins.

# Plugins

The more specific a functionality became, the more awkward it felt to be integrated in the above core-Architecture. When we started to make exchange specific functionality, we wanted to protect the core-Architecture from deluting. Therefore we created a plugin-concept which allows to have the above concepts replicated in it there own self-contained standalone units.

We try now to implement bigger chunks of functionality in plugins. Maybe even core-functionality might be placed with "core-plugins" in the future. Those are placed in `src/specterext`. But plugins can also live in there own repos, have their own release-lifecycle and be used by Specter like any other dependency as well. For more information about plugins see [Third Party Service Integrations](./services/services.md).