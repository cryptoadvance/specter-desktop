# Adding Nodes or NodeTypes

The whole programming-model is based on the Bitcoin-Core API. So we need Bitcoin Core nodes or elements nodes or at least something which behaves like that. So for the Spectrum Integration, we made extending the node possible. This is a short description of how that has been done and which extensionpoints might be helpfull here.

So to create your own Node, derive from `AbstractNode`:

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

That class will need its own `fromJson` method. Overwrite the `node_info_template` method to specify your own template for the info-page which comes up if you click on a fully configured and functional node in the upper left corner. In order to smuggle your node into existence, you could potentially use the `callback_after_serverpy_init_app` callback. Have a look how the spectrum-extension did it [here](https://github.com/cryptoadvance/spectrum/pull/9/files#diff-82be7977bfa33bdbb0a448c7a03b43de90c4749565bef6737d6d516956ff0823R51-R62). Alternatively, you could create your own frontend in your controller and maybe additionally adjust the `WelcomeVm` model class as described in the frontend section.

If the `node_settings` are clicked for that node, we also expect that you have a `node_settings` endpoint in your controller. Otherwise there will be errors. Something like:

```
@yourextension_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias=None):
    [...]
    return render_template(...
 ```