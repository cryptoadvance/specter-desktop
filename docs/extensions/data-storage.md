## Data storage
As an extension developer, you have the choice to completely manage your own persistence. Don't hesitate to completely do your own thing. However, if your requirements are not that complicated, you can rely/use one of two options: You either have data which need encryption (via the passwords of the users) or you don't have that requirement.

## ServiceEncryptedStorage
Some `Services` will require user secrets (e.g. API key and secret). Each Specter `User` will have their own on-disk encrypted `ServiceEncryptedStorage` with filename `<username>_services.json`. Note that the user's secrets for all `Services` will be stored in this one file.

This is built upon the `GenericDataManager` class which supports optional encrypted fields. In this case all fields are encrypted. The `GenericDataManager` encryption can only be unlocked by each `User`'s individual `user_secret` that itself is stored encrypted on-disk; it is decrypted to memory when the `User` logs in.

For this reason `Services` cannot be activated unless the user is signing in with a password-protected account (the default no-password `admin` account will not work).

_Note: During development if the Flask server is restarted or auto-reloads, the user's decrypted `user_secret` will no longer be in memory. The Flask context will still consider the user logged in after restart, but code that relies on having access to the `ServiceEncryptedStorage` will throw an error and/or prompt the user to log in again._

It is up to each `Service` implementation to decide what data is stored; the `ServiceEncryptedStorage` simply takes arbitrary json in and delivers it back out.

This is also where `Service`-wide configuration or other information should be stored, _**even if it is not secret**_ (see above intro about not polluting other existing data stores).

## ServiceEncryptedStorageManager
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

## `ServiceUnencryptedStorage`
A disadvantage of the `ServiceEncryptedStorage` is, that the user needs to be freshly logged in in order to be able to decrypt the secrets. If you want to avoid that login but your extension should still store data on disk, you can use the `ServiceUnencryptedStorage`.

In parallel with the `ServiceEncryptedStorageManager` there is also a `ServiceUnencryptedStorageManager` which is used exactly the same way.

## `ServiceAnnotationsStorage`
Annotations are any address specific or transaction specific data from a `Service` that we might want to present to the user (not yet implemented). Example: a `Service` that integrates with a onchain store would have product/order data associated with a utxo. That additional data could be imported by the `Service` and stored as an annotation. This annotation data could then be displayed to the user when viewing the details for that particular address or tx.

Annotations are stored on a per-wallet and per-`Service` basis as _unencrypted_ on-disk data (filename: `<wallet_alias>_<service>.json`).

_Note: current `Service` implementations have not yet needed this feature so displaying annotations is not yet implemented._

## Data Storage Class Diagram

Unfortunately, the two unencrypted classes are derived from the encrypted one rather than having it the other way around or having abstract classes. This makes the diagram maybe a bit confusing.

[![](https://mermaid.ink/img/pako:eNqVVMFuwjAM_ZUqJzaVw66IIU0D7bRd0G6VItO4LFvqoCRlqhj_PpeWASLduhyiqH7v-dlOsxO5VSgmIjfg_VzD2kGZUcKr3Z-Q0Ol8DgGegWCNLpl-jcfJEt1W57ig3NWbgGoZrONoS-oJXjBfCaPcPxI-ENkAQVvyF7RHS4VeVw5WBpea1gaDpZbZZ6eT_9VyzMK18_8oZeIuE8l4fMsn4tOQRvZm7FPra24XZgLjK4--38BFTe1-uCORAe3acLOk1KSDlCOPpkgTxSBZWKPQpUlniUcnP7C-f7GENycmQYnSFvLdc7zQBk-hn1r4OxrlTxFjQY3ORKSHbUfcn3vuqTFm_MIyt4h3pX1zraTCA_0sX0b9ya5varxPB7DUKk0-wfC1HSh_PeJdFB7_Mc6sTKf--Hk2G96769lHhJrlW7xc1bJp538qGpQjJnVqhUhFia4ErfiROwhlIrxhiZmY8FFhAZUJmciogVYbHj8ulOb8YlKA8ZgKqIJd1pSLSXAVHkHdW9mh9t9YNMxZ)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNqVVMFuwjAM_ZUqJzaVw66IIU0D7bRd0G6VItO4LFvqoCRlqhj_PpeWASLduhyiqH7v-dlOsxO5VSgmIjfg_VzD2kGZUcKr3Z-Q0Ol8DgGegWCNLpl-jcfJEt1W57ig3NWbgGoZrONoS-oJXjBfCaPcPxI-ENkAQVvyF7RHS4VeVw5WBpea1gaDpZbZZ6eT_9VyzMK18_8oZeIuE8l4fMsn4tOQRvZm7FPra24XZgLjK4--38BFTe1-uCORAe3acLOk1KSDlCOPpkgTxSBZWKPQpUlniUcnP7C-f7GENycmQYnSFvLdc7zQBk-hn1r4OxrlTxFjQY3ORKSHbUfcn3vuqTFm_MIyt4h3pX1zraTCA_0sX0b9ya5varxPB7DUKk0-wfC1HSh_PeJdFB7_Mc6sTKf--Hk2G96769lHhJrlW7xc1bJp538qGpQjJnVqhUhFia4ErfiROwhlIrxhiZmY8FFhAZUJmciogVYbHj8ulOb8YlKA8ZgKqIJd1pSLSXAVHkHdW9mh9t9YNMxZ)

## Implementation Notes
Efforts has been taken to provide `Service` data storage that is separate from existing data stores in order to keep those areas clean and simple. Where touchpoints are unavoidable, they are kept to the absolute bare minimum (e.g. `User.services` list in `users.json`, `Address.service_id` field).