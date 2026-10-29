const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const contexto = vm.createContext({});
vm.runInContext(fs.readFileSync('src/web/js/mensagens.js', 'utf8'), contexto);
const tratar = contexto.mensagemErroAmigavel;
assert.equal(tratar('Informe o valor do empréstimo.'), 'Informe o valor do empréstimo.');
for (const texto of ["cannot import name 'projetar_anos' from 'src.simulador'", 'TypeError: x is undefined', 'C:\\Users\\pessoa\\dados.db']) {
    assert(!tratar(texto).includes(texto));
    assert(tratar(texto).includes('Tente novamente'));
}
assert(tratar({message: 'Failed to fetch'}).includes('Verifique sua conexão'));
assert(tratar(null).includes('Tente novamente'));
console.log('Mensagens: validações preservadas, falhas técnicas tratadas e orientação de conexão verificada.');
