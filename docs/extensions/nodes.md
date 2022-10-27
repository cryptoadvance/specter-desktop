# Adding Nodes or NodeTypes

The whole programming-model is based on the Bitcoin-Core API. So we need Bitcoin Core Nodes or Elements Nodes or at least something which behaves like that. So for the Spektrum Integration, we made Extending the Node possible. This is a short description og how that has been done and which extension-points might be helpfull here.

So To Create your own Node, Derive from `AbstractNode`., you have to specify the modules containing subclasses of `Device` in `service.py`:

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

It will need it's own `fromJson` method. Overwrite the `node_info_template` method to specify your own template. In order to smuggle your node into existence, you could potentially use the `callback_after_serverpy_init_app` callback. Have a look how the spectrum-extension did it [here](https://github.com/cryptoadvance/spectrum/pull/9/files#diff-82be7977bfa33bdbb0a448c7a03b43de90c4749565bef6737d6d516956ff0823R51-R62).

If the `node_settings` are clicked for that Node, we also expect that you have a `node_settings` endpoint in your controller. Otherwise there will be errors. Something like:

```
@yourextension_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias=None):
    [...]
    return render_template(...
 ```