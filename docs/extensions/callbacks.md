
# Callback methods

Callback methods will get called from within Specter Desktop Core for various reasons. You can implement them in your service-class in order to react on those occasions.

Checkout the `cryptoadvance.specter.services.callbacks` file for all the specific callbacks.

Your Extension is also able to specify your own callback-methods. What does that mean? Let's assume you have specified a callback `my_callback`. So anywhere in your code, once or as many times you like, you can call:
```
app.specter.ext_manager.execute_ext_callbacks(my_callback, "any", params, you="like")
```
So the `ext_manager` will then take care that all extensions are called which register that function. What exactly is called for each funtion and what's returned, depends on the `return_style` (see below). This is the same for all callbacks, no matter whether one which is called by core or by an extension.

Some important one is the `after_serverpy_init_app` which passes a `Scheduler` class which can be used to setup regular tasks. A list of currently implemented callback-methods along with their descriptions are available in [`/src/cryptoadvance/specter/services/callbacks.py`](https://github.com/cryptoadvance/specter-desktop/blob/master/src/cryptoadvance/specter/services/callbacks.py).

Those callback functions come in different `return_styles`: `collect` and `middleware`. 

## Return Style `collect`

Collect is the simpler style. In this model, all extensions are called exactly with the same arguments and the return-value is a dict whit the id's of the extensions as keys and the return-value as value.

As an example, let's consider you specify this callback:
```python
# in service.py
class MyExtension(Service):
    callbacks = ["mynym.specterext.myextension.callbacks"]

    def some_method(self):
        returnvalues = app.specter.ext_manager.execute_ext_callbacks(my_callback, "any", params, you="like")
# in callbacks.py
class my_callback(Callback)
    id = "my_callback"
```
So now let's consider that there are two extensions which are speficied like this:
```python

class ExtensionA(Service):
    id = "extensiona"
    def callback_my_callback(any, params, you=like):
        return { any:like }

class ExtensionB(Service):
    id = "extensionb"
    def callback_my_callback(any, params, you=like):
        return ["some","array"]
```

So in this case, the returnvalues would like this:
```json
{
    "extensiona": {"any":"like"},
    "extensionb": ["some","array"]
}
```

## Return Style `middleware`

In the case of middleware, you can pass one object which will in turn passed to all extensions which registered that callback. Have a look at the `adjust_view_model` callback which is explained in detail in the frontend-section.