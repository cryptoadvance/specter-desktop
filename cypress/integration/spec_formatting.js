import { capitalize, numberWithCommas } from '../../src/cryptoadvance/specter/static/helper-modules/formatting.js'

describe('Unit tests of formatting JS functions', () => {
    before(() => {
        cy.visit('/')
    })

    it('Test capitalize function', () => {
        expect(capitalize('satoshi')).to.equal('Satoshi')
        expect(capitalize('satoshi nakamoto')).to.equal('Satoshi nakamoto')
    })

    it('Test numberWithCommas function', () => {
        expect(numberWithCommas('1000')).to.equal('1,000')
        expect(numberWithCommas('1000000')).to.equal('1,000,000')
        expect(numberWithCommas(1000)).to.equal('1,000')
        expect(numberWithCommas(1000000)).to.equal('1,000,000')
        expect(numberWithCommas('0.1')).to.equal('0.1')
        expect(numberWithCommas(0.1)).to.equal('0.1')
    })
    
})
