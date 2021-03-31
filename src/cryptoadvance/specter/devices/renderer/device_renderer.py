from jinja2 import Environment, FunctionLoader


class DeviceRenderer:
    def __init__(self, device):
        self.device = device
        self.env = Environment(loader=FunctionLoader(self.load_template))

    @classmethod
    def load_template(cls, name):
        def func_not_found():  # just in case we dont have the function
            return "<p>Something is missing here</p>"

        func = getattr(cls, "template_" + name, func_not_found)
        return func()

    def render(self, name):
        template = self.env.get_template(name)
        return template.render(device=self.device)

    @classmethod
    def template_device_scripts(cls):
        return """
        async function signMessageOnDevice() {
			hidePageOverlay();
			let signature = await signMessage(
				'{{ device.device_type }}',
				document.getElementById('message').value,
				document.getElementById('messageDerivationPath').value
			);
			document.getElementById('signature-label').style.display = 'block';
			document.getElementById('signature').innerText = signature;
			showPageOverlay('message-signing');
			showNotification('Message was signed successfully!')
		}
        """
