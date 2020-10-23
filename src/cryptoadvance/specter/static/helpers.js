window.addEventListener('load', (event) => {
	let main = document.getElementsByTagName("main")[0];
	main.addEventListener('click', (event) => {
		document.getElementById("side-content").classList.remove("active");
	});
	let menubtn = document.getElementById("menubtn");
	menubtn.addEventListener('click', (event) => {
		document.getElementById("side-content").classList.add("active");
		event.stopPropagation();
	});
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
		element.textContent = value
		var selection = document.getSelection();
		var range = document.createRange();
		range.selectNode(element);
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