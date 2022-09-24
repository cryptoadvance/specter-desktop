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
	formData.append("csrf_token", csrf_token)
	d = {
			method: method_str,
		}
	if (method_str == 'POST') {
		d['body'] = formData;
	}

	const response = await fetch(url, d);
	if(response.status != 200){
		showError(await response.text());
		console.log(`Error while calling ${url} with ${method_str} ${formData}`)
		return
	}
	return await response.json();
}







function format_btc_amount_as_sats(
    value,
    enable_digit_formatting=False,
) {
	const locale = 'en-US';
    var s = round(parseFloat(value) * 1e8).toLocaleString(locale, { 
		minimumFractionDigits: 8, 
		maximumFractionDigits: 8 
	  }); 

	let thousandsSeparator = Number(1000).toLocaleString(locale).charAt(1);
	let decimalSeparator = Number(1.1).toLocaleString(locale).charAt(1);
	  
    // combine the thousandsSeparator with the left number to an array
    var array = [];
    for (var i in s){
		var letter = s[i];
        if (letter == thousandsSeparator){
            array[-1] += letter;
		} else {
			array.push(letter);
		}
	}

    if (enable_digit_formatting){
        if (len(array) >= 4){
            var left_index = len(array) >= 6 ? -6 : -len(array);
            array[left_index] = `<span class="thousand-digits-in-sats-amount">${array[left_index]}`;
            array[-4] = `${array[-4]}</span>`;
		}

        var left_index = len(array) >= 3 ? -3: -len(array);
        array[left_index] = `<span class="last-digits-in-sats-amount">${array[left_index]}`;
        array[-1] = `${array[-1]}</span>`;
	}

    return array.join('')
}

function format_btc_amount(
    value,
    maximum_digits_to_strip=7,
    minimum_digits_to_strip=6,
    enable_digit_formatting=True,
){
    /*
    Formats the btc amount such that it can be right aligned such
    that the decimal separator will be always at the same x position.
    Stripping trailing 0's is done via just making the 0's transparent.
    Args:
        value (Union[float, str]): Will convert string to float.
            The float is expected to be in the unit (L)BTC with 8 relevant digits
        maximum_digits_to_strip (int, optional): No more than maximum_digits_to_strip
            trailing 0's will be stripped. Defaults to 7.
        minimum_digits_to_strip (int, optional): Only strip any trailing 0's if
            there are at least minimum_digits_to_strip. Defaults to 6.
        enable_digit_formatting (bool, optional): Will group the Satoshis into blocks of 3,
            e.g. 0.03 123 456, and color the blocks. Defaults to True.
    Returns:
        str: The formatted btc amount as html code.
    */
	const locale = 'en-US';
	var formatted_amount = parseFloat(value).toLocaleString(locale, { 
		minimumFractionDigits: 8, 
		maximumFractionDigits: 8 
	  }); 

	let thousandsSeparator = Number(1000).toLocaleString(locale).charAt(1);
	let decimalSeparator = Number(1.1).toLocaleString(locale).charAt(1);

    var count_digits_that_can_be_stripped = 0;
    for (var j in formatted_amount){
		var i = formatted_amount.length - j;
        if (formatted_amount[i] == "0"){
            count_digits_that_can_be_stripped += 1;
            continue
		}
        break
	}

    var array = Array.from(formatted_amount);
    if (count_digits_that_can_be_stripped >= minimum_digits_to_strip){
        // loop through the float number, e.g. 0.03 000 000, from the right and replace 0's or the '.' until you hit anything != 0
		for (var j in array){
			var i = array.length - j;
            if ((array[i] == "0") && (len(array) - i <= maximum_digits_to_strip)){
                array[
                    i
                ] = `<span class="unselectable transparent-text">${array[i]}</span>`;
                // since this digit == 0, then continue the loop and check the next digit
                continue
			}
            // the following if branch is only relevant if last_digits_to_strip == 8, i.e. all digits can be stripped
            else if (formatted_amount[i] == "."){
                array[i] = `<span class="unselectable transparent-text">${array[i]}</span>`;
                // since this character == '.', then the loop must be broken now
			}
            // always break the loop. Only the digit == 0 can prevent this break
            break
		}

    if (enable_digit_formatting){
        array[-6] = `<span class="thousand-digits-in-btc-amount">${array[-6]}`;
        array[-4] = `${array[-4]}</span>`;
        array[-3] = `<span class="last-digits-in-btc-amount">${array[-3]}`;
        array[-1] = `${array[-1]}</span>`;
	}

    return array.join('');
}

