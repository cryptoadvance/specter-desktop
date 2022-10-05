function capitalize(str){
	return str.charAt(0).toUpperCase()+str.substring(1);
}

function numberWithCommas(x) {
	x = parseFloat(x).toString();
	if (x.split(".").length > 1) {
		return x.split(".")[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",") + '.' + x.split(".")[1];
	}
    return x.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export { capitalize, numberWithCommas }
