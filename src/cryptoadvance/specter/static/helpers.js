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
