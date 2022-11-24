function showPacman(){
	document.getElementById('pacman').style.display='flex';
}

function showPageOverlay(container_id) {
	// Transfer the content to the popup overlay div
	document.getElementById("page_overlay_popup_content").appendChild(document.getElementById(container_id));

	// Show the whole-screen dimming layer
	var overlay = document.getElementById("page_overlay");
	overlay.style.display = "flex";

	// Position and show the popup
	var overlayPopup = document.getElementById("page_overlay_popup");
	overlayPopup.style.display = "block";

	// Show the content
	var pageContent = document.getElementById("page_overlay_popup_content").children[0];
	pageContent.style.display = "block";

	window.scrollTo(0, 0);
}

function hidePageOverlay() {
	if (overlayIsActive()) {
		// Transfer the content back into a holder div
		var holder = document.createElement("div");
		holder.style.display = "none";
		document.body.appendChild(holder);
		holder.appendChild(document.getElementById(document.getElementById("page_overlay_popup_content").children[0].id));

		var overlay = document.getElementById("page_overlay");
		overlay.style.display = "none";

		var overlayPopup = document.getElementById("page_overlay_popup");
		overlayPopup.style.display = "none";
		cancelOverlay();
	}
}

function overlayIsActive(){
	let el = document.getElementById("page_overlay");
	return el.style.display != "none";
}

document.addEventListener("DOMContentLoaded", function(){
	// Handler when the DOM is fully loaded

	document.addEventListener("keyup", function(e) {
		// Dismiss popup with ESC button
		if (e.keyCode == 27) {
			var elem = document.getElementById("page_overlay");
			// If it's visible... (using jQuery's visibility test)
			if (!!( elem.offsetWidth || elem.offsetHeight || elem.getClientRects().length )) {
				cancelOverlay();
			}
		}
	});

	Specter.common.attachEventListener("page_overlay", "click", function(e) {
		// Ignore clicks on children
		if(e.target !== e.currentTarget) return;
		cancelOverlay();
	});
});

function cancelOverlay() {
	hidePageOverlay();
}


export { showPacman, showPageOverlay, hidePageOverlay, overlayIsActive, cancelOverlay }
