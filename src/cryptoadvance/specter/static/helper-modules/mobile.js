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

export { toggleMobileNav }