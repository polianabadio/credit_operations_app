const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = vm.createContext({document: {addEventListener() {}}});
const script = fs.readFileSync(path.join(__dirname, '..', 'src', 'web', 'js', 'eel-main.js'), 'utf8');
vm.runInContext(script, context);

assert.equal(context.lerValorRequisitado('1234567,89').formatado, 'R$ 1.234.567,89');
assert.equal(context.lerValorRequisitado('R$ 1.234.567,89').numero, 1234567.89);
assert.equal(context.lerValorRequisitado('1.234').numero, 1234);
assert.equal(context.lerValorRequisitado('1,5').formatado, 'R$ 1,50');
assert.equal(context.lerValorRequisitado('R$ 1.000.0000000,00').formatado, 'R$ 10.000.000.000,00');
assert.equal(context.lerValorRequisitado('R$ 1.000,000').formatado, 'R$ 1.000,00');
assert.equal(context.lerValorRequisitado('').numero, 0);
assert.throws(() => context.lerValorRequisitado('1,234'), /duas casas decimais/);
assert.throws(() => context.lerValorRequisitado('4854889498749849849849498'), /muito alto/);
assert.throws(() => context.lerValorRequisitado('-1'), /negativo/);

console.log('Valor requisitado em reais validado.');
