# Adding Nodes or NodeTypes

The whole programming model is based on the Bitcoin-Core API. So we need Bitcoin Core nodes or Elements nodes or at least something which behaves like that. So for the Spectrum integration, we made extending the Node class possible. This is a short description on how that has been done and which extension points might be helpful here.

To create your own node, derive from `AbstractNode`. You have to specify the modules containing subclasses of `Device` in `service.py`:

```
from cryptoadvance.specter.node import AbstractNode

class MyNode(AbstractNode):
    # [...]
    @classmethod
    def from_json(cls, node_dict, *args, **kwargs):
      [...]

    def node_info_template(self):
      return "spectrum/components/spectrum_info.jinja"
```

It will need its own `from_json` method (overwriting the `from_json` method of the PersistentObject). Overwrite the `node_info_template` method to specify your own template. In order to plugin in your node , you can use the `callback_after_serverpy_init_app` callback. Have a look how the Spectrum extension did it [here](https://github.com/cryptoadvance/spectrum/pull/9/files#diff-82be7977bfa33bdbb0a448c7a03b43de90c4749565bef6737d6d516956ff0823R51-R62).

If the `node_settings` are clicked for that node, we also expect that you have a `node_settings` endpoint in your controller. Otherwise there will be errors. Something like:

```
@yourextension_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias=None):
    [...]
    return render_template(...
 ```