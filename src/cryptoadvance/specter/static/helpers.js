import * as formatModule from './helper-modules/format.js'
import * as commonModule from './helper-modules/common.js'
import * as mobileModule from './helper-modules/mobile.js'
import * as overlayModule from './helper-modules/overlay.js'

// The scope of functions inside a module is not global, putting them on the window object makes them accessible outside of the module. 
// See: https://stackoverflow.com/questions/44590393/es6-modules-undefined-onclick-function-after-import
// A central JS Specter object which itself has different objects to attach JS functions as methods to
// For example: 
// The capitalize function from ./helper-modules/format.js would be accessed like so:
// Specter.format.capitalize()

function attachToSpecter(name, helperFunction, category) {
  if (typeof(window.Specter) === 'undefined') {
    window.Specter = {} 
  }
  if (typeof(Specter[`${category}`]) === 'undefined') {
    Specter[`${category}`] = {}
  }
  // TODO: Do we have to test if that key already exists?
  Specter[`${category}`][`${name}`] = helperFunction
}

// Adding format functions to Specter.format
for (let functionName in formatModule) {
	attachToSpecter(functionName, formatModule[functionName], 'format')	
}

// Adding common functions to Specter.common
for (let functionName in commonModule) {
	attachToSpecter(functionName, commonModule[functionName], 'common')	
}

// Adding mobile functions to Specter.mobile
for (let functionName in mobileModule) {
	attachToSpecter(functionName, mobileModule[functionName], 'mobile')	
}

// Adding overlay functions to Specter.mobile
for (let functionName in overlayModule) {
	attachToSpecter(functionName, overlayModule[functionName], 'overlay')	
}

// TODOS!
// window.copyText = copyText // TODO
// window.toggleMobileNav = toggleMobileNav // TODO

window.addEventListener('load', (event) => {
	let main = document.getElementsByTagName("main")[0];
	main.addEventListener('click', (event) => {
		let side_content = document.getElementById("side-content")
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

document.documentElement.style.setProperty('--mobileDistanceElementBottomHeight', `${Math.max(0, window.outerHeight - window.innerHeight)}px`);

// Enable navigation loader
window.addEventListener('beforeunload', function (e) {
	// half a second delay before we show it
	window.setTimeout(()=>{
		document.getElementById("pageloader").style.display = 'block';
	}, 200);
});

console.debug('Loaded helpers.js')
