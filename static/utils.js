// static/utils.js

/**
 * Formata um valor numérico como uma string de moeda em Reais (BRL).
 * @param {number | string} value - O valor a ser formatado.
 * @returns {string} O valor formatado como, por exemplo, "R$ 1.234,56".
 */
function formatCurrency(value) {
    const number = parseFloat(value || 0);
    return `R$ ${number.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
}

/**
 * Formata um valor numérico como uma string de percentual.
 * @param {number | string} value - O valor a ser formatado.
 * @returns {string} O valor formatado como, por exemplo, "15,00%".
 */
function formatPercent(value) {
    const number = parseFloat(value || 0);
    return `${number.toFixed(2).replace('.', ',')}%`;
}

/**
 * Converte uma string de moeda formatada (BRL) para um número float.
 * @param {string} currencyString - A string a ser convertida (ex: "R$ 1.234,56").
 * @returns {number} O valor numérico correspondente (ex: 1234.56).
 */
function parseCurrency(currencyString) {
    if (typeof currencyString !== 'string') return 0;
    // Remove "R$", espaços, e troca o separador de milhar por nada, e a vírgula decimal por ponto.
    const numberString = currencyString.replace('R$', '').trim().replace(/\./g, '').replace(',', '.');
    return parseFloat(numberString) || 0;
}

/**
 * Converte uma string de percentual formatada para um número float.
 * @param {string} percentString - A string a ser convertida (ex: "15,00%").
 * @returns {number} O valor numérico correspondente (ex: 15.00).
 */
function parsePercent(percentString) {
    if (typeof percentString !== 'string') return 0;
    const numberString = percentString.replace('%', '').trim().replace(',', '.');
    return parseFloat(numberString) || 0;
}