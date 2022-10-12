import { capitalize, formatUnitLabel , formatLiquidUnitLabel, rstrip, formatLiquidAmountAndUnitArray,
	formatLiquidAmountsAndUnitsArray, formatLiquidAmountsAndUnits,
	formatBtcAmountAndUnitArray, formatBtcAmountAndUnit, formatBtcAmount, formatPrice } from './helper-modules/formatting.js'
import { copyText, send_request, showError, showNotification, wait } from './helper-modules/common.js'
import { toggleMobileNav } from './helper-modules/mobile.js'

// The scope of functions inside a module is not global, putting them on the window object makes them accessible outside of the module. 
// See: https://stackoverflow.com/questions/44590393/es6-modules-undefined-onclick-function-after-import
window.capitalize = capitalize
window.formatUnitLabel = formatUnitLabel
window.formatLiquidUnitLabel = formatLiquidUnitLabel
window.rstrip = rstrip
window.formatLiquidAmountAndUnitArray = formatLiquidAmountAndUnitArray
window.formatLiquidAmountsAndUnitsArray = formatLiquidAmountsAndUnitsArray
window.formatLiquidAmountsAndUnits = formatLiquidAmountsAndUnits
window.formatBtcAmountAndUnitArray = formatBtcAmountAndUnitArray
window.formatBtcAmountAndUnit = formatBtcAmountAndUnit
window.formatBtcAmount = formatBtcAmount
window.formatPrice = formatPrice

window.copyText = copyText
window.send_request = send_request
window.showError = showError
window.showNotification = showNotification
window.wait = wait
window.toggleMobileNav = toggleMobileNav

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
