# Third-Party Service Integrations

A developer's guide for Specter Desktop `Service` integrations.


## Basic Code Philosophy
As much as possible, each `Service` implementation should be entirely self-contained with little or no custom code altering existing/core Specter functionality.

Effort has been taken to provide `Service` data storage that is separate from existing data stores in order to keep those areas clean and simple. Where touchpoints are unavoidable, they are kept to the absolute bare minimum (e.g. `User.services` list, `Address.service_id` field).


## `Address`-Level Integration
An `Address` can be associated with a `Service` (e.g. addr X received a smash buy from `Service` Foo) via the `Address.service_id` field.

A `Service` can also "reserve" and `Address` for future use by setting `Address.service_id`. The normal "Receive" UI will automatically skip any reserved `Address`es when generating a new receive addr. The reserved addresses are interleaved with ready-to-use addresses so that we don't create any potentially confusing wallet gaps (e.g. addrs 4, 6, and 8 are reserved but addrs 3, 5, and 7 are available).

Users can also manually associate an existing `Address` with a `Service` (this is useful when the user has info that the particular `Service` api can't provide for whatever reason).

_Note: TODO: manually un-reserve an `Address` from a `Service`._


## Basic Code Structure
All `Service`-related code should be contained within `cryptoadvance.specter.services`. The base components are:


### `Service` Base Class
Defines the base `Service` class that all service integrations must inherit from. This is wired to enable `Service` auto-discovery. Any feature that is common to most or all `Service` integrations should be implemented here.

Each `Service` must specify a unique `Service.id` that is just a short string (e.g. "swan"). This is the main identifier throughout the code.


### `ServiceManager`
Simple manager that contains all `Service`s. Performs the `Service` auto-discovery at startup and filters availability by each `Service`'s release level (i.e. alpha, beta, etc).


### `ServiceEncryptedStorage`
Most `Service`s will require user secrets (e.g. API key and secret). Each Specter `User` will have their own on-disk encrypted `ServiceEncryptedStorage` with filename `<username>_services.json`. Note that the user's secrets for all `Service`s will be stored in this one file.

This is built upon the `GenericDataManager` class which supports optional encrypted fields. In this case all fields are encrypted. The `GenericDataManager` encryption can only be unlocked by each `User`'s individual `user_secret` that itself is stored encrypted on-disk; it is decrypted to memory when the `User` logs in.

For this reason `Service`s cannot be activated unless the user is signing in with a password-protected account (the default no-password `admin` account will not work).

_Note: during development if the Flask server is restarted or auto-reloads, the user's decrypted `user_secret` will no longer be in memory. The Flask context will still consider the user logged in after restart, but code that relies on having access to the `ServiceEncryptedStorage` will throw an error and/or prompt the user to log in again._

It is up to each `Service` implementation to decide what data is stored; the `ServiceEncryptedStorage` simply takes arbitrary json in and delivers it back out.

This is also where `Service`-wide configuration or other information should be stored, _**even if it is not secret**_ (see above intro about not polluting other existing data stores).


### `ServiceEncryptedStorageManager`
Because the `ServiceEncryptedStorage` is specific to each individual user, this manager provides convenient access to automatically retrieve the `current_user` from the Flask context and provide the correct user's `ServiceEncryptedStorage`. It is implemented as a `Singleton` which can be retrieved simply by importing the class and calling `get_instance()`.

This simplifies code to just asking for:
```
from .service_encrypted_storage import ServiceEncryptedStorageManager

ServiceEncryptedStorageManager.get_instance().get_current_user_service_data(service_id=some_service_id)
```


### `ServiceAnnotationsStorage`
Annotations are any address-specific or transaction-specific data from a `Service` that we might want to present to the user. Example: a `Service` that integrates with a onchain storefront would have product/order data associated with a utxo. That additional data could be imported by the `Service` and stored as an annotation. This annotation data could then be displayed to the user when viewing the details for that particular address or tx.

Annotations are stored on a per-wallet and per-`Service` basis as _unencrypted_ on-disk data (filename: `<wallet_alias>_<service>.json`).

_Note: current `Service` implementations have not yet needed this feature so displaying annotations is not yet implemented._


### `controller.py`
The minimal url routes for `Service` selection and management.
