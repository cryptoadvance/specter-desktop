window.addEventListener('load', (event) => {
	let main = document.getElementsByTagName("main")[0];
	main.addEventListener('click', (event) => {
		side_content = document.getElementById("side-content")
		if (side_content != null) {
			side_content.classList.remove("active");
		}
	});
	let menubtn = document.getElementById("menubtn");
	if (menubtn != null) {
		menubtn.addEventListener('click', (event) => {
			document.getElementById("side-content").classList.add("active");
			event.stopPropagation();
		});
	}
});

document.addEventListener("errormsg", (e)=>{
	if(!("timeout" in e.detail)){
		e.detail.timeout = 0;
	}
	showError(e.detail.message, e.detail.timeout);
});
document.addEventListener("notification", (e)=>{
	if(!("timeout" in e.detail)){
		e.detail.timeout = 3000;
	}
	showNotification(e.detail.message, e.detail.timeout);
});

document.addEventListener("updateAddressLabel", function (e) {
	document.querySelectorAll('address-label').forEach(el => {
		let event = new CustomEvent('updateAddressLabel', { detail: e.detail });
		return el.dispatchEvent(event);
	});

	// TODO: Needed currently for all custom elements containing <address-label>
	// Find an alternative which would work regardless of shadowRoot
	if (document.querySelector('tx-table')) {
		document.querySelector('tx-table').shadowRoot.querySelectorAll('tx-row').forEach(el => {
			el.shadowRoot.querySelectorAll('address-label').forEach(el => {
				let event = new CustomEvent('updateAddressLabel', { detail: e.detail });
				return el.dispatchEvent(event);
			});
		});
	}

	if (document.querySelector('addresses-table')) {
		document.querySelector('addresses-table').shadowRoot.querySelectorAll('address-row').forEach(el => {
			el.shadowRoot.querySelectorAll('address-label').forEach(el => {
				let event = new CustomEvent('updateAddressLabel', { detail: e.detail });
				return el.dispatchEvent(event);
			});
		});
	}
	
	if (document.querySelector('address-data')) {
		document.querySelector('address-data').shadowRoot.querySelectorAll('address-label').forEach(el => {
			let event = new CustomEvent('updateAddressLabel', { detail: e.detail });
			return el.dispatchEvent(event);
		});
	}
});

// Clicking somewhere else than on the edit label section cancels the label editing
document.addEventListener("click", (e) => {
	addressesTableComponent = document.querySelector('addresses-table')
	txTableComponent = document.querySelector('tx-table')
	addressDataComponent = document.querySelector('address-data')
	const path = e.composedPath()
	const clickedElement = path[0]
	const parentElement = path[1]
	if (addressesTableComponent) {
		addressesTableComponent.shadowRoot.querySelectorAll('address-row').forEach(addressRow => {
			const addressLabel = addressRow.shadowRoot.querySelector('address-label')
			if (addressLabel.isEditing) {
				console.log("Clicking somewhere else on the screen. Canceling editing.")
				addressLabel.cancelEditing()
			}
		})
	}
	else if (txTableComponent) {
		txTableComponent.shadowRoot.querySelectorAll('tx-row').forEach(txRow => {
			const addressLabel = txRow.shadowRoot.querySelector('address-label')
			// In the tx labeling there also "labels" ("X Recipients") which aren't label components
			if (addressLabel !== null && addressLabel.isEditing) {
				console.log("Clicking somewhere else on the screen. Canceling editing.")
				addressLabel.cancelEditing()
			}
		})
	}
	// Can't use else if here: Address data is a pop-up so addresses or tx table are still in the DOM
	if (addressDataComponent) {
		addressDataComponent.shadowRoot.querySelectorAll('address-label').forEach(addressLabel => {
			if (addressLabel.isEditing) {
				console.log("Clicking somewhere else on the screen. Canceling editing.")
				addressLabel.cancelEditing()
			}
		})
	}
})

document.documentElement.style.setProperty('--mobileDistanceElementBottomHeight', `${Math.max(0, window.outerHeight - window.innerHeight)}px`);

function showError(msg, timeout=0) {
	return showNotification(msg, timeout, "error");
}
function showNotification(msg, timeout=3000, type="primary") {
	let el = document.createElement("message-box");
	el.setAttribute("type", type);
	el.setAttribute("timeout", timeout);
	el.innerHTML = msg;
	document.getElementById("messages").appendChild(el);
	el.addEventListener('click', (e)=>{
		document.getElementById("messages").removeChild(el);
	});
	return el;
}

function copyText(value, msg) {
	try {
		var element = document.createElement("p");
		document.getElementsByTagName("body")[0].appendChild(element);
		element.textContent = value;
		var selection = document.getSelection();
		var range = document.createRange();
		range.selectNodeContents(element);
		selection.removeAllRanges();
		selection.addRange(range);
		document.execCommand("copy");
		selection.removeAllRanges();
		document.getElementsByTagName("body")[0].removeChild(element);
		showNotification(msg);
	}
	catch (err) {
		showError('Unable to copy text');
	}
}
async function wait(ms){
	return new Promise(resolve => {
		setTimeout(resolve, ms);
	});
}
function capitalize(str){
	return str.charAt(0).toUpperCase()+str.substring(1);
}

// Enable navigation loader
window.addEventListener('beforeunload', function (e) {
	// half a second delay before we show it
	window.setTimeout(()=>{
		document.getElementById("pageloader").style.display = 'block';
	}, 200);
});

// toggle a navbar on mobile view
function toggleMobileNav(btn, openImg, collapseImg) {
	var x = btn.parentNode;
	if (x.className === "row collapse-on-mobile") {
		x.className += " responsive";
		btn.children[0].src = collapseImg;
	} else {
		x.className = "row collapse-on-mobile";
		btn.children[0].src = openImg;
	}
}

function numberWithCommas(x) {
	x = parseFloat(x).toString();
	if (x.split(".").length > 1) {
		return x.split(".")[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",") + '.' + x.split(".")[1];
	}
    return x.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}


async function send_request(url, method_str, csrf_token, formData) {
	if (!formData) {
		formData = new FormData();
	}
	const headers = new Headers();
 	headers.append('Accept', 'application/json');
	formData.append("csrf_token", csrf_token)
	d = {
			method: method_str,
			headers: headers
		}
	if (method_str == 'POST') {
		d['body'] = formData;
	}
	try {
		const response = await fetch(url, d);
		if(response.status != 200){
			showError(await response.text());
			console.log(`Error while calling ${url} with ${method_str} ${formData}`)
			return {"error": `Error while calling ${url} with ${method_str} ${formData}` }
		}
		let jsonResponse = await response.json();
		console.log(`${method_str} call response:`)
		console.log(jsonResponse)
		if (typeof(jsonResponse) === 'boolean') {
			return {}
		}
		else if (jsonResponse !== null && jsonResponse.error) {
			showError(`${jsonResponse.error}`)
			return jsonResponse
		}
		return jsonResponse
	}
	catch(error) {
		showError(`Error occured durch fetch call: ${error}`)
		return { 'error': error}
	}
}