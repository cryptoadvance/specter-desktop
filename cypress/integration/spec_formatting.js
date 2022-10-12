
/* setting global js variables for helpers.js */
const is_liquid = false;
const is_testnet = true;
const price_check_enabled = false;
const hide_sensitive_info_enabled = false;
const specter_unit = 'BTC';
const alt_rate = '10001';
const alt_symbol = '$';

import { capitalize, formatUnitLabel , formatLiquidUnitLabel, rstrip, formatLiquidAmountAndUnitArray,
	formatLiquidAmountsAndUnitsArray, formatLiquidAmountsAndUnits,
	formatBtcAmountAndUnitArray, formatBtcAmountAndUnit, formatBtcAmount, formatPrice } from '../../src/cryptoadvance/specter/static/helper-modules/formatting.js'
    
    

describe('Unit tests of formatting JS functions', () => {
    before(() => {
        cy.visit('/')
    })

    it('Test capitalize function', () => {
        expect(capitalize('satoshi')).to.equal('Satoshi')
        expect(capitalize('satoshi nakamoto')).to.equal('Satoshi nakamoto')
    })

    it('Test formatUnitLabel', () => {
        expect(formatUnitLabel('btc', false)).to.equal('BTC')
    })

    it('Test formatPrice', () => {
        expect(formatPrice(0.1, '$', 10001, true)).to.equal('tobedone')
    })


        
})
