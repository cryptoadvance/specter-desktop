// TODO: how to import it both in module and in global code?
/** adds keys to txt area **/
function addKeys(data) {
	var keysarea = document.getElementById("txt");
	// only add non-duplicates
	let loaded = keysarea.value.split("\n");
	let candidates = data.split("\n");
	candidates = candidates.filter((e) => !loaded.includes(e));
	if (candidates.length == 0) {
		showNotification(`{{ _("No new keys are added.") }}`);
	} else {
		showNotification(`Added ${candidates.length} keys.`);
	}
	let final = candidates.concat(loaded);
	keysarea.value = final.join("\n");
}
function setDeviceType(type) {
	var deviceType = document.getElementById("device_type");
	// if deviceType exists and it's empty
	if (deviceType != null && deviceType.value == "") {
		deviceType.value = type;
		let name = type[0].toUpperCase() + type.slice(1);
		showNotification(`Device type changed to ${name}`);
	}
}
