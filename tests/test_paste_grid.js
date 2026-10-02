const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = vm.createContext({document: {addEventListener() {}}});
const script = fs.readFileSync(path.join(__dirname, '..', 'src', 'web', 'js', 'eel-main.js'), 'utf8');
vm.runInContext(script, context);

const paste = (text, row, column, totalRows) =>
    Array.from(context.prepararColagemMonetaria(text, row, column, totalRows), cell => ({...cell}));

assert.deepEqual(paste('1.234,567\r\n2.000,00\r\n', 0, 0, 2), [
    {linha: 0, coluna: 0, formatado: 'R$ 1.234,56'},
    {linha: 1, coluna: 0, formatado: 'R$ 2.000,00'},
]);
assert.deepEqual(paste('1.000,00\t2.000,00\n3.000,00\t4.000,00', 0, 0, 2), [
    {linha: 0, coluna: 0, formatado: 'R$ 1.000,00'},
    {linha: 0, coluna: 1, formatado: 'R$ 2.000,00'},
    {linha: 1, coluna: 0, formatado: 'R$ 3.000,00'},
    {linha: 1, coluna: 1, formatado: 'R$ 4.000,00'},
]);
assert.deepEqual(paste('5,00\n6,00', 1, 1, 3), [
    {linha: 1, coluna: 1, formatado: 'R$ 5,00'},
    {linha: 2, coluna: 1, formatado: 'R$ 6,00'},
]);
assert.deepEqual(paste('R$ 2.000.000000000,00', 0, 0, 1), [
    {linha: 0, coluna: 0, formatado: 'R$ 2.000.000.000.000,00'},
]);
assert.equal(context.normalizarValorMonetario('R$ 2.000.000000000,00').formatado,
    'R$ 2.000.000.000.000,00');
assert.throws(() => paste('1\n2\n3', 0, 0, 2), /excede os anos/);
assert.throws(() => paste('1\t2', 0, 1, 2), /excede as duas colunas/);
assert.throws(() => paste('1\tvalor inválido', 0, 0, 2), /use o formato/);
assert.throws(() => paste('1\n-12.905.414,88', 0, 0, 2), /Linha 2, coluna 1: valor negativo/);

console.log('Colagem em grade validada.');
