# Architectural notes

Specter Desktop and Specter Cloud are flask applications and follow typical model-view-controller principles. The model part is covered by a number of business objects and managers who are responsible for maintaining/managing those. Currently we have these managers:

## Managers

* GenericDataManager is abstracting persistence aspects and most managers which are persisting json data are derived from this one.
* The ConfigManager manages the configuration persisted in config.json. It's not supposed to have any side-effects. Setting and getting only with a lot of validation and computing while setting/getting.
* A DeviceManager mainly manages the persistence of a device-json structure compliant to helper.load_jsons.py.
* NodeManager manages internal and external nodes.
* UserManager manages all stuff regarding Users.
* Similarly, the WalletManager manages all wallet stuff. 
        
## Views and blueprints
The controller part is covered by "server_endpoints". Those are split up in “blueprints”. This is a way to split the urls in sub-urls. These sub-urls are loosely related to the business-objects: `/welcome`, `/auth`, `/devices`, `/nodes`, `/price`, `/services` (should be renamed "`/plugins`"), `/settings`, `/setup`, `/wallets`.

## Views
The views are effectively jinja2 templates which can extend from higher order ones and have placeholders which templates can then override. The `base.jinja` lays out the basic layout having a block for the `sidebar` and a `main` block (plus `head` and `scripts` ). Some blueprints (`/settings`,`/wallets`) span up a top-level navigation. In that case, the template extends from its specific blueprint-base template which in turn provides a block called `content` and the template decides which menu point is active:
```
{% extends "wallet/components/wallet_tab.jinja" %}
{% set tab = 'receive' %}
{% block content %}
...
```
This is also a pattern used for plugins.

# Plugins

The more specific a functionality became, the more awkward it felt to integrate it in the core architecture. When we started to make exchange specific functionality, we wanted to protect the core architecture. Therefore, we created a plugin concept which allows to have the above concepts replicated in their own self-contained standalone units. 

We now try to implement bigger chunks of functionality in plugins. Maybe, even core functionality might be implemented in "core plugins" in the future. Internal plugins are placed in `src/specterext`. But, plugins can also live in there own repos, have their own release lifecycle and be used by Specter like any other dependency. For more information about plugins see [Third Party Service Integrations](./extensions.md) where we also discuss the nuances between plugins and extensions.

# The Crypto Engine
The Crypto Engine consists of a bunch of classes which partially are based on Embit.
The documentation here is incomplete but will better over time.

## psbt classes

[![](https://mermaid.ink/img/pako:eNqVU11PgzAU_StNnzTO_QDiizoffNKEPRkS0rWXrRF6SXurLHP_3QKOsjHNhIRczj0997M7LlEBT7gshXMLLdZWVJlh4blfObJC0rJ5REPQELv7ur1laQ2SwC6bS1ipxBp64hg54jyb2tMlxBdPx8y_Y7-mD8vM9G_L7iqcntn1XsZulJbEDNAn2vcBXICTVteElqlo9u79WHjoSxT80CYnzFvdq-uIoqcz8AlyTrsrPcqvEEumXV5pAxNQboRZT2ELEnTIaz14QjuYUMqCcwOmTcGcoFxU6A0NcFGiINZ9T1wXJB_HHCuIGNOmHoWnc-FXWwLHqNGKHVHbhv4jkdEaxUxGIBvJTVL5XbZdt6g3n88H29dKEIxGXVisTsffYWEzjQvLqdEMFfAZr8BWQqtwS7sAGacNVJDxJJgKCuFLynhmWmof60npsKU8KUTpYMaFJ0y3RvKErIcD6eeyD6xamDfEw__-G-B6VVQ?type=png)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNqVU11PgzAU_StNnzTO_QDiizoffNKEPRkS0rWXrRF6SXurLHP_3QKOsjHNhIRczj0997M7LlEBT7gshXMLLdZWVJlh4blfObJC0rJ5REPQELv7ur1laQ2SwC6bS1ipxBp64hg54jyb2tMlxBdPx8y_Y7-mD8vM9G_L7iqcntn1XsZulJbEDNAn2vcBXICTVteElqlo9u79WHjoSxT80CYnzFvdq-uIoqcz8AlyTrsrPcqvEEumXV5pAxNQboRZT2ELEnTIaz14QjuYUMqCcwOmTcGcoFxU6A0NcFGiINZ9T1wXJB_HHCuIGNOmHoWnc-FXWwLHqNGKHVHbhv4jkdEaxUxGIBvJTVL5XbZdt6g3n88H29dKEIxGXVisTsffYWEzjQvLqdEMFfAZr8BWQqtwS7sAGacNVJDxJJgKCuFLynhmWmof60npsKU8KUTpYMaFJ0y3RvKErIcD6eeyD6xamDfEw__-G-B6VVQ)

## embit classes
Here is a diagram of all the classes from the embit library. No properties/attributes or methods are in there, yet.

[![](https://mermaid.ink/img/pako:eNqFk19rgzAQwL-K5Ln9ArKnYtnGNiqzbDDycsZrDcREkstGcX73xT9tLejqSzx_Py935NIwYQpkMRMKnEskHC1UXBfSoiBpdPT6znUUnm2VS9qAw-jhd70ewhc8TWCIBvaU3ILrX5k8aiBvcZ6KUhtrgzSXNfW5kmJhy9TKbyBc2jfBnod-UqByVkmzzT4Tph5Lu4QDfda1p2W883TLZ5IvtGxlTbPoU5JG52bZ3oJ20B_QPd5Xfk8a6udjsn4UokdlclAT6UPiT3N22qnatbdMsxIs_oMypCllK1ahrUAWYSqb7jNnVGKFnMXhtcADeEWccd0G1ddFOPdtIclYFh9AOVwx8GSykxYsJuvxLI3DfbFq0F_GXGPsk7yN16Fb2j-RrgZR?type=png)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNqFk19rgzAQwL-K5Ln9ArKnYtnGNiqzbDDycsZrDcREkstGcX73xT9tLejqSzx_Py935NIwYQpkMRMKnEskHC1UXBfSoiBpdPT6znUUnm2VS9qAw-jhd70ewhc8TWCIBvaU3ILrX5k8aiBvcZ6KUhtrgzSXNfW5kmJhy9TKbyBc2jfBnod-UqByVkmzzT4Tph5Lu4QDfda1p2W883TLZ5IvtGxlTbPoU5JG52bZ3oJ20B_QPd5Xfk8a6udjsn4UokdlclAT6UPiT3N22qnatbdMsxIs_oMypCllK1ahrUAWYSqb7jNnVGKFnMXhtcADeEWccd0G1ddFOPdtIclYFh9AOVwx8GSykxYsJuvxLI3DfbFq0F_GXGPsk7yN16Fb2j-RrgZR)

## About Tor

Tor in general means two things: 
* Using the Tor network for outgoing connection to confuse outgoing traffic
* Use Tor to create a tor-hidden-service which often enough is also used as a kind of "poor man's firewall" and to avoid the details of a port-forwarding setup

Tor support is possible either via a custom or the built-in installation. The type of installation is stored in `specter.tor_type` which is redirecting to the `config_manager` which by default returns `builtin`. Another valid value is `custom` and initially we have `none`.
Other important tor-details are the check whether the tor_deamon_is_running (`specter.is_tor_dameon_running()`) and whether the torbrowser is installed (`os.path.isfile(app.specter.torbrowser_path)`).