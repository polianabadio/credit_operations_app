const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('src/web/js/eel-main.js', 'utf8');
const campos = {
    'caed-data-referencia': {value: '2026-10-07'},
    'fator-rcl': {value: '', setCustomValidity(texto) { this.validationMessage = texto; }},
    'caed-fator-origem': {textContent: ''}
};
let taxa = '2.031208231';
let invalidacoes = 0;
const contexto = vm.createContext({
    document: {getElementById: id => campos[id]},
    marcarSimulacaoDesatualizada() { invalidacoes++; },
    eel: {
        obter_fator_projecao_py: () => async () => ({taxa_percentual: taxa}),
        salvar_fator_projecao_py: valor => async () => {
            if (valor === 'inválido') return {status: 'erro', mensagem: 'Taxa inválida'};
            taxa = valor.replace('%', '').replace(',', '.');
            return {status: 'sucesso', fator: taxa};
        }
    }
});
vm.runInContext(script.slice(script.indexOf('async function carregarFatorCaed()'),
    script.indexOf('function normalizarPagamentoCaed(')), contexto);
(async () => {
    await contexto.carregarFatorCaed();
    assert.equal(campos['fator-rcl'].value, '2,031208231%');
    campos['fator-rcl'].value = '3,5%';
    await contexto.salvarTaxaCaed();
    campos['fator-rcl'].value = '';
    await contexto.carregarFatorCaed();
    assert.equal(campos['fator-rcl'].value, '3,5%');
    campos['fator-rcl'].value = 'inválido';
    await contexto.salvarTaxaCaed();
    assert(campos['fator-rcl'].validationMessage);
    assert.equal(taxa, '3.5');
    assert.equal(invalidacoes, 2);
    console.log('Taxa CAED: percentual, salvamento, reutilização e erro validados.');
})().catch(erro => { console.error(erro); process.exitCode = 1; });
