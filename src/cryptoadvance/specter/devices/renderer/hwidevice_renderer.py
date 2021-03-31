from .device_renderer import DeviceRenderer


class HWIDeviceRenderer(DeviceRenderer):
    def render_button_sign_message(self):
        return ""

    @classmethod
    def template_button_sign_message(cls):
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
        """

    @classmethod
    def template_button_toggle_password(cls):
        return """
        	<button type="button" class="btn centered" onclick="togglePassphrase('{{ device.device_type }}')">Toggle device passphrase</button>
        """
