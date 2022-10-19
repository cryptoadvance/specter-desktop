# Data storage
As an extension developer, you have the choice to completely manage your own persistence. Don't hesitate to completely do your own thing. However, if your requirements are not that complicated, you can rely/use one of two options: You either have data which need encryption (via the passwords of the users) or you don't have that requirement.

## ServiceEncryptedStorage
Some `Services` will require user secrets (e.g. API key and secret). Each Specter `User` will have their own on-disk encrypted `ServiceEncryptedStorage` with filename `<username>_services.json`. Note that the user's secrets for all `Services` will be stored in this one file.

This is built upon the `GenericDataManager` class which supports optional encrypted fields. In this case all fields are encrypted. The `GenericDataManager` encryption can only be unlocked by each `User`'s individual `user_secret` that itself is stored encrypted on-disk; it is decrypted to memory when the `User` logs in.

For this reason `Services` cannot be activated unless the user is signing in with a password-protected account (the default no-password `admin` account will not work).

_Note: During development if the Flask server is restarted or auto-reloads, the user's decrypted `user_secret` will no longer be in memory. The Flask context will still consider the user logged in after restart, but code that relies on having access to the `ServiceEncryptedStorage` will throw an error and/or prompt the user to log in again._

It is up to each `Service` implementation to decide what data is stored; the `ServiceEncryptedStorage` simply takes arbitrary json in and delivers it back out.

This is also where `Service`-wide configuration or other information should be stored, _**even if it is not secret**_ (see above intro about not polluting other existing data stores).

## ServiceEncryptedStorageManager
Because the `ServiceEncryptedStorage` is specific to each individual user, this manager provides convenient access to automatically retrieve the `current_user` from the Flask context and provide the correct user's `ServiceEncryptedStorage`.

This simplifies code to just asking for:
```python
from .service_encrypted_storage import ServiceEncryptedStorageManager

app.specter.service_encrypted_storage_manager.get_current_user_service_data(service_id=some_service_id)
```

As a further convenience, the `Service` base class itself encapsulates `Service`-aware access to this per-`User` encrypted storage:
```python
@classmethod
def get_current_user_service_data(cls) -> dict:
    return app.specter.service_encrypted_storage_manager.get_current_user_service_data(service_id=cls.id)
```

## `ServiceUnencryptedStorage`
A disadvantage of the `ServiceEncryptedStorage` is, that the user needs to be freshly logged in in order to be able to decrypt the secrets. If you want to avoid that login but your extension should still store data on disk, you can use the `ServiceUnencryptedStorage`.

In parallel with the `ServiceEncryptedStorageManager` there is also a `ServiceUnencryptedStorageManager` which is used exactly the same way.

## `ServiceAnnotationsStorage`
Annotations are any address specific or transaction specific data from a `Service` that we might want to present to the user (not yet implemented). Example: a `Service` that integrates with a onchain store would have product/order data associated with a utxo. That additional data could be imported by the `Service` and stored as an annotation. This annotation data could then be displayed to the user when viewing the details for that particular address or tx.

Annotations are stored on a per-wallet and per-`Service` basis as _unencrypted_ on-disk data (filename: `<wallet_alias>_<service>.json`).

_Note: current `Service` implementations have not yet needed this feature so displaying annotations is not yet implemented._

## Data Storage Class Diagram

Unfortunately, the two unencrypted classes are derived from the encrypted one rather than having it the other way around or having abstract classes. This makes the diagram maybe a bit confusing.

[![](https://mermaid.ink/img/pako:eNqVVD1PwzAQ_SuRp4KSgTWCAakVEywVC4pkXeNLMTjnynaKotL_jpukTaLGEDxYdt579-4j8oHlWiBLWa7A2qWErYEyo8ivdn9CQiPzJTh4BoItmuj-O0miNZq9zHFFual3DsXaaePRVhQAR8pXwkntH4aPRNqBk5rsHMupENfOHWtWpIzdZSxKklt_In-a04igYyhaqDkd7AWeX1m04QRGNbV7M-OJBh9a-LQ4lyQd5wuLqogj4Um80EqgiaMuJd96_on1w4smvOmVBCVyXfAP6_FCKuyhSy3-Oyphe0RpEItBEG5h3wmPw5wDNU4lPkrZt8jvQlrYKOQCG_nAL6Ow2fWfNt2nhsyliKMvUArnhr8e8eE3emC8g5RsC_BNzU9l_8d5HCys7DNkMSvRlCCFfzsaXcbcO5aYsdQfBZjPjGV04lU7PxJcCem9WFqAshgzqJxe15Sz1JkKz6Tu_bmwdkBvWp_vxx_pzJiR)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNqVVD1PwzAQ_SuRp4KSgTWCAakVEywVC4pkXeNLMTjnynaKotL_jpukTaLGEDxYdt579-4j8oHlWiBLWa7A2qWErYEyo8ivdn9CQiPzJTh4BoItmuj-O0miNZq9zHFFual3DsXaaePRVhQAR8pXwkntH4aPRNqBk5rsHMupENfOHWtWpIzdZSxKklt_In-a04igYyhaqDkd7AWeX1m04QRGNbV7M-OJBh9a-LQ4lyQd5wuLqogj4Um80EqgiaMuJd96_on1w4smvOmVBCVyXfAP6_FCKuyhSy3-Oyphe0RpEItBEG5h3wmPw5wDNU4lPkrZt8jvQlrYKOQCG_nAL6Ow2fWfNt2nhsyliKMvUArnhr8e8eE3emC8g5RsC_BNzU9l_8d5HCys7DNkMSvRlCCFfzsaXcbcO5aYsdQfBZjPjGV04lU7PxJcCem9WFqAshgzqJxe15Sz1JkKz6Tu_bmwdkBvWp_vxx_pzJiR)

## Implementation Notes
Efforts has been taken to provide `Service` data storage that is separate from existing data stores in order to keep those areas clean and simple. Where touchpoints are unavoidable, they are kept to the absolute bare minimum (e.g. `User.services` list in `users.json`, `Address.service_id` field).