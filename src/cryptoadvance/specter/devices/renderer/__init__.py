from jinja2 import Environment, FunctionLoader, select_autoescape
from flask import current_app as app, url_for


class DeviceRenderer:
    def __init__(self, device):
        self.device = device
        self.env = Environment(
            loader=FunctionLoader(self.load_template),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def load_template(self, name):
        def func_not_found(self):  # just in case we dont have the function
            # raise Exception ?
            # return "<p>Something is missing here</p>" ?
            return ""

        func = getattr(self.__class__, "template_" + name, func_not_found)
        return func(self)

    def render(self, name):
        template = self.env.get_template(name)
        return template.render(device=self.device, url_for=url_for)

    def template_multi_add_keys(self):
        return """
			<button id="add_keys" type="submit" name="action" value="add_keys" class="btn centered">Add more keys</button>
        """

    def template_device_scripts(self):
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


# Difficult to have this in the inheritance-tree as Specter is not derived from HWIDevice
# So we'll define it here and return it in HWIDeviceRenderer and Specter
template_multi_sign_message_string = """
        	<button type="button" class="btn centered" onclick="showPageOverlay('message-signing')">Sign message on device</button>
			<div id="message-signing" class="hidden" style="text-align: left;">
				Derivation path:<input type="text" id="messageDerivationPath" type="text" value="" placeholder="e.g. m/84h/0h/0h/0/0"><br><br>
				Message:<br>
				<textarea id="message" placeholder="Enter the message you would like to sign" style="font-size: 0.95em;"></textarea>
				<span id="signature-label" class="hidden">Message signature:</span>
				<p style="word-break: break-all; margin-top: 5px;" id="signature" title="Copy message signature" class="explorer-link" onclick="copyText(this.innerText, 'Copied message signature')">
				</p>
				<button type="button" class="btn centered" onclick="signMessageOnDevice();">Sign message on device</button>
			</div>
            <br>
"""


class HWIDeviceRenderer(DeviceRenderer):
    def render_button_sign_message(self):
        return ""

    def template_multi_sign_message(self):
        return template_multi_sign_message_string

    def template_button_toggle_password(self):
        if self.device.supports_hwi_toggle_passphrase:
            return """
                <button type="button" class="btn centered" onclick="showPageOverlay('message-signing')">Sign message on device</button>
                <div id="message-signing" class="hidden" style="text-align: left;">
                    Derivation path:<input type="text" id="messageDerivationPath" type="text" value="" placeholder="e.g. m/84h/0h/0h/0/0"><br><br>
                    Message:<br>
                    <textarea id="message" placeholder="Enter the message you would like to sign" style="font-size: 0.95em;"></textarea>
                    <span id="signature-label" class="hidden">Message signature:</span>
                    <p style="word-break: break-all; margin-top: 5px;" id="signature" title="Copy message signature" class="explorer-link" onclick="copyText(this.innerText, 'Copied message signature')">
                    </p>
                    <button type="button" class="btn centered" onclick="signMessageOnDevice();">Sign message on device</button>
                </div>
                <br>
            """
        else:
            return ""


class TrezorRenderer(HWIDeviceRenderer):
    pass


class ColdCardRenderer(HWIDeviceRenderer):
    pass


class SpecterRenderer(HWIDeviceRenderer):
    def template_multi_sign_message(self):
        return template_multi_sign_message_string
