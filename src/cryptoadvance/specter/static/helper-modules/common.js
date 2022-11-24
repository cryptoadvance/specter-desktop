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

async function send_request(url, method_str, csrf_token, formData) {
	if (!formData) {
		formData = new FormData();
	}
	formData.append("csrf_token", csrf_token)
	let d = {
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

async function wait(ms){
	return new Promise(resolve => {
		setTimeout(resolve, ms);
	});
}


function attachEventListener(id, type, f){
	const element = document.getElementById(id);
	if (element){
		element.addEventListener(type, f);  	
	}	
}

export { copyText, send_request, showError, showNotification, wait, attachEventListener }