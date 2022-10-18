
/* setting global js variables for helpers.js */
// const is_liquid = false;
const is_testnet = true;
const price_check_enabled = false;
const hide_sensitive_info_enabled = false;
const specter_unit = 'BTC';
const alt_rate = '10001';
const alt_symbol = '$';

// import { capitalize, formatUnitLabel , formatLiquidUnitLabel, rstrip, formatLiquidAmountAndUnitArray,
// 	formatLiquidAmountsAndUnitsArray, formatLiquidAmountsAndUnits,
// 	formatBtcAmountAndUnitArray, formatBtcAmountAndUnit, formatBtcAmount, formatPrice } from '../../src/cryptoadvance/specter/static/helper-modules/formatting.js'
    
import { Specter } from '../../src/cryptoadvance/specter/static/helpers.js'

describe('Tests of JS format functions', () => {
    before(() => {
        cy.visit('/')
    })
    it('Test capitalize function', () => {
        expect(window.Specter.format.capitalize('satoshi')).to.equal('Satoshi') // window is needed here to access Specter object
        expect(window.Specter.format.capitalize('satoshi nakamoto')).to.equal('Satoshi nakamoto')
    })

    it('Test rstrip', () => {
        expect(window.Specter.format.rstrip('10000000', '0')).to.equal('1')
        expect(window.Specter.format.rstrip('liaaaaaaa', 'a')).to.equal('li')
        expect(window.Specter.format.rstrip('10,', ',')).to.equal('10')
    })

    it.skip('Test unitLabel', () => {
        expect(window.Specter.format.unitLabel('btc', false, false, true)).to.equal('BTC')
    })

    it.skip('Test price', () => {
        expect(window.Specter.price(0.1, '$', 10001, true)).to.equal('tobedone')
    })

    it.skip('Test price', () => {
        expect(window.Specter.price(0.1, '$', 10001, true)).to.equal('tobedone')
    })

        
})
