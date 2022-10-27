function capitalize(str){
	return str.charAt(0).toUpperCase()+str.substring(1);
}

/*
Formats the btc amount as sats. 
Args:
value (Union[float, str]): (in BTC) Will convert string to float. 
enableDigitFormatting (bool, optional): Will group the Satoshis into blocks of 3,
	e.g. 3 123 456, and color the blocks. Defaults to false.
Returns:
str: The formatted btc amount as html code.
*/
function internalFormatBtcAmountAsSats(
	value,
	enableDigitFormatting=false,
) {
	// for now 'en-US' is hard-coded, but this could be generalized to null
	// such that the browsers locale would be used.
	const locale = 'en-US';
	value = parseFloat(value);
	if (isNaN(value)){
		return null;  
	}
	var s = (value * 1e8).toLocaleString(locale, { 
		minimumFractionDigits: 0, 
		maximumFractionDigits: 0 
	});         

	// use thousandsSeparator and decimalSeparator to simplify future generalization of locale
	let thousandsSeparator = Number(1000).toLocaleString(locale).charAt(1);
	let decimalSeparator = Number(1.1).toLocaleString(locale).charAt(1);
	
	// combine the thousandsSeparator with the left number to an array
	var array = [];
	for (var i in s){
		var letter = s[i];
		if (letter == thousandsSeparator){
			// Remark: i is not necessarily equal to array.length-1
			// since array.length != s.length (generally) after this loop ends.
			// Here we add letter to the last entry in the array.
			array[array.length-1] += letter;
		} else {
			array.push(letter);
		}
	}

	if (enableDigitFormatting){
		const l = array.length;
		if (l >= 4){
			var left_index = l >= 6 ? l-6 : 0;
			array[left_index] = `<span class="thousand-digits-in-sats-amount">${array[left_index]}`;
			array[l-4] = `${array[l-4]}</span>`;
		}

		var left_index = l >= 3 ? l-3: 0;
		array[left_index] = `<span class="last-digits-in-sats-amount">${array[left_index]}`;
		array[l-1] = `${array[l-1]}</span>`;
	}

	return array.join('')
}

/*
	Formats the btc amount such that it can be right aligned such
	that the decimal separator will be always at the same x position.
	Stripping trailing 0's is done via just making the 0's transparent.
	Args:
		value (Union[float, str]): (in BTC) Will convert string to float.
			The float is expected to be in the unit (L)BTC with 8 relevant digits
		maximumDigitsToStrip (int, optional): No more than maximumDigitsToStrip
			trailing 0's will be stripped. Defaults to 7.
		minimumDigitsToStrip (int, optional): Only strip any trailing 0's if
			there are at least minimumDigitsToStrip. Defaults to 6.
		enableDigitFormatting (bool, optional): Will group the Satoshis into blocks of 3,
			e.g. 0.03 123 456, and color the blocks. Defaults to True.
	Returns:
		str: The formatted btc amount as html code.
	*/

function internalFormatBtcAmount(
	value,
	maximumDigitsToStrip=7,
	minimumDigitsToStrip=6,
	enableDigitFormatting=true,
	hideStripped=false
){
	value = parseFloat(value);
	if (isNaN(value)){
		return null;
	}
	
	// for now 'en-US' is hard-coded, but this could be generalized to null
	// such that the browsers locale would be used.
	const locale = 'en-US';
	var formatted_amount = (value).toLocaleString(locale, { 
		minimumFractionDigits: 8, 
		maximumFractionDigits: 8 
	}); 

	var array = Array.from(formatted_amount);
	// use thousandsSeparator and decimalSeparator to simplify future generalization of locale
	let thousandsSeparator = Number(1000).toLocaleString(locale).charAt(1);
	let decimalSeparator = Number(1.1).toLocaleString(locale).charAt(1);

	var countDigitsThatCanBeStripped = 0;
	for (var j in array){
		var i = array.length - j - 1;
		if (array[i] == "0"){
			countDigitsThatCanBeStripped += 1;
			continue
		}
		break
	}

	if (countDigitsThatCanBeStripped >= minimumDigitsToStrip){
		// loop through the float number, e.g. 0.03 000 000, from the right and replace 0's or the '.' until you hit anything != 0
		for (var j in array){
			var i = array.length - j - 1;
			if ((array[i] == "0") && (array.length - i <= maximumDigitsToStrip)){
				array[i] = `<span class="unselectable transparent-text ${hideStripped ? 'hidden' : ''}">${array[i]}</span>`;
				// since this digit == 0, then continue the loop and check the next digit
				continue
			}
			// the following if branch is only relevant if last_digits_to_strip == 8, i.e. all digits can be stripped
			else if (formatted_amount[i] == decimalSeparator){
				array[i] = `<span class="unselectable transparent-text ${hideStripped ? 'hidden' : ''}">${array[i]}</span>`;
				// since this character == '.', then the loop must be broken now
			}
			// always break the loop. Only the digit == 0 can prevent this break
			break
		}
	}

	const l = array.length;
	if (enableDigitFormatting){
		array[l-6] = `<span class="thousand-digits-in-btc-amount">${array[l-6]}`;
		array[l-4] = `${array[l-4]}</span>`;
		array[l-3] = `<span class="last-digits-in-btc-amount">${array[l-3]}`;
		array[l-1] = `${array[l-1]}</span>`;
	}

	return array.join('');
}

// Puts the price in a "note" span.  preText is separator text 
function internalFormatPriceAsNote(price, preText=''){
	return `<span class="note">${preText}(${price})</span>`
}

// Determines if an unit (e.g. from a tx output) is "BTC", "LBTC", "tBTC", "tLBTC"
// null or "" will also return true
function internalUnitLabelIsBTC(unit){
	if (!unit){
		return true            
	} 
	unit = unit.toUpperCase();
	return ([null, "", "LBTC", "BTC", "TBTC", "TLBTC"].indexOf(unit) > -1)
}

// Formats the network independent units to network dependent units,
// e.g.: btc -> tBTC,  sat --> tsat ,  btc --> tLBTC, sat --> tLsat 
function unitLabel(enableHTML=true) { 
	const convertToSat = Specter.unit == 'sat';
	let newLabel
	// standardize the incoming unit
	if (['BTC', 'LBTC', 'TBTC', 'TLBTC'].includes(Specter.unit.toUpperCase())){
		newLabel = 'BTC';
	}
	if (['SAT', 'LSAT', 'TSAT', 'TLSAT'].includes(Specter.unit.toUpperCase())){
		newLabel = 'sat';
	}

	// convert to sat if necessary
	if (convertToSat && newLabel == 'BTC') {
		newLabel = 'sat';
	}

	if (Specter.isLiquid){
		if (!newLabel.startsWith("t")){
			newLabel = "L" + newLabel;
		}
	}
	if (Specter.isTestnet){
		if (!newLabel.startsWith("t")){
			newLabel = "t" + newLabel;
		}
	}
	return enableHTML ? `<nobr>${newLabel}</nobr>` : newLabel;
}

// Formats the network independent units to network dependent units,
// e.g.: btc -> tBTC,  sat --> tsat ,  btc --> tLBTC, sat --> tLsat 
function internalFormatLiquidUnitLabel(asset, assetLabel, targetUnit=Specter.unit){ 
	let newLabel = assetLabel;
	let enableHTML
	// if the asset is BTC, then replace BTC with a nicely formatted (and converted Bitcoin unit), e.g. tLsat
	if (internalUnitLabelIsBTC(assetLabel)){
		newLabel = unitLabel(targetUnit, enableHTML=false); 
	}

	return `<nobr><asset-label data-asset="${asset}" data-label="${newLabel}"></asset-label></nobr>`;
}

// strips the right end of the text with the pattern
function rstrip(text, pattern) { 
	return text.replace(new RegExp(pattern + "*$"),''); 
};

// Formats value and unit
// e.g. ["0.22569496", "<asset-label data-asset="65846551" data-label="tLBTC"></asset-label>"]
function liquidAmountAndUnitArray(value, asset, assetLabel, targetUnit=Specter.unit, hideStripped=true){
	if (Specter.hideSensitiveInfo){
		return ["#########"];}
	else{
		if (value < 0 || value == null){
			return ["Confidential"]}

		const convertToSat = targetUnit == 'sat';            
		var formattedUnitLabel = internalFormatLiquidUnitLabel(targetUnit, assetLabel, targetUnit);        
		var formattedValue = (convertToSat && internalUnitLabelIsBTC(assetLabel)) ? internalFormatBtcAmountAsSats(value) : internalFormatBtcAmount(
																						value,
																						7,
																						6,
																						true,
																						hideStripped);

		return [formattedValue, formattedUnitLabel];              
	}
}

// Returns a formatted amount and unti.  It can handle multiple, or a single assets, assetLabels  as input
// e.g. ["0.22569496", "<asset-label data-asset="65846551" data-label="tLBTC"></asset-label>"]
function internalLiquidAmountsAndUnitsArray(value, assets, assetLabels, targetUnit=Specter.unit, hideStripped=true){
	if (Specter.hideSensitiveInfo){
		return ["#########"];}
	else{
		if (value < 0 || value == null){
			return ["Confidential"]}

		
		if (Array.isArray(assets)) {
			value = Array.isArray(value) ? value[0]: value;  // only take the first value, because multiple values are not displayed
				// multiple assets
			let unique_assets = assets.filter((v, i, a) => { return a.indexOf(v) === i });
			if (unique_assets.length == 1){
				return liquidAmountAndUnitArray(value, assets[0], assetLabels[0]);
			}else if (unique_assets.length == 0){
				return [''];
			}else{
				return [`${unique_assets.length} assets`];
			}
		}else{
			return liquidAmountAndUnitArray(value, assets, assetLabels, targetUnit, hideStripped);
		}    
	}
}

// Returns a formatted amount and unti.  It can handle multiple, or a single assets, assetLabels  as input
// e.g. "0.22569496 <asset-label data-asset="65846551" data-label="tLBTC"></asset-label>"
function liquidAmountsAndUnits(value, asset, assetLabel, targetUnit=Specter.unit, hideStripped=true){
	return internalLiquidAmountsAndUnitsArray(value, asset, assetLabel, targetUnit, hideStripped).join(' ');  
}

// Formats the valueInBTC (e.g. from a tx output) to an array
// e.g. ["0.22569496", "tBTC"]
// by default targetUnit will be set to BTC for liquid to prevent any conversion of valueInBTC
function btcAmountAndUnitArray(valueInBTC, targetUnit=Specter.unit, hideStripped=true){
	if (Specter.hideSensitiveInfo){
		return ["#########"];}
	else{
		if (valueInBTC == null){
			return ["Unknown"]};

		const convertToSat = targetUnit == 'sat';
		var formattedUnitLabel = Specter.format.unitLabel(targetUnit);        
		var formattedValue = convertToSat ? internalFormatBtcAmountAsSats(valueInBTC) : internalFormatBtcAmount(
																							valueInBTC,
																							7,
																							6,
																							true,
																							hideStripped);
		return [formattedValue, formattedUnitLabel];  
	}
}

// Formats the valueInBTC (e.g. from a tx output) to an "formattedValue formattedUnitLabel"
// e.g. "0.22569496 tBTC"
function btcAmountAndUnit(valueInBTC, targetUnit=Specter.unit, hideStripped=true){
	return btcAmountAndUnitArray(valueInBTC, targetUnit, hideStripped).join(' ');  
}

// Formats the valueInBTC (e.g. from a tx output) to an "formattedValue"
// e.g. "0.22569496"
function btcAmount(valueInBTC, targetUnit=Specter.unit, hideStripped=true){
	return btcAmountAndUnitArray(valueInBTC, targetUnit, hideStripped)[0];  
}

// Calculates and formats the price as a span class="note"
function price(valueInBTC, 
					unit='BTC', 
					symbol=Specter.altSymbol, 
					price=Specter.altRate,
					wrapInSpan=true,
					){        
	if (!Specter.priceCheck){
		return '';}
	else {		
		if (Specter.hideSensitiveInfo){
			return "#########";}
		else{
			if ((valueInBTC < 0 || valueInBTC == null) && Specter.isLiquid){
				return ""}
			if (valueInBTC == null){
				return ""};

			var formattedPrice = "";
			if (valueInBTC) {
				if(internalUnitLabelIsBTC(unit)){
					if (price && symbol) {
						const locale = 'en-US';
						let thousandsSeparator = Number(1000).toLocaleString(locale).charAt(1);
						let decimalSeparator = Number(1.1).toLocaleString(locale).charAt(1);
						var formatted_amount = (parseFloat(valueInBTC)*parseFloat(price)).toLocaleString(locale, { 
							minimumFractionDigits: 2, 
							maximumFractionDigits: 2 
						});
						formatted_amount = rstrip(formatted_amount, '0')
						formatted_amount = rstrip(formatted_amount, `\\${decimalSeparator}`)
						formattedPrice = (["$", "£"].includes(symbol)) ? `${symbol}${formatted_amount}` : `${formatted_amount}${symbol}`;
						formattedPrice = wrapInSpan ? internalFormatPriceAsNote(formattedPrice, ' ') : formattedPrice;
					}
				}
			}
			return formattedPrice;
		}
	}
}

export { capitalize, rstrip, unitLabel, btcAmountAndUnit, btcAmountAndUnitArray, btcAmount, price, liquidAmountAndUnitArray, liquidAmountsAndUnits }
