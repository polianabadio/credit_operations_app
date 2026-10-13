const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../src/web/js/eel-main.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../src/web/main.html'), 'utf8');
assert(!html.includes('id="linhas-hipotese-2"'));
assert(!html.includes('id="secao-hipotese-2"'));
assert(html.includes('id="caed-cobertura-completa"'));
assert(html.includes('inputmode="decimal" aria-describedby="caed-fator-origem"'));

function preparar() {
    const classe = () => { const valores = new Set(['hidden']); return {
        contains: v => valores.has(v), add: v => valores.add(v), remove: v => valores.delete(v)
    }; };
    const elemento = (id, value = '') => ({id, value, checked: false, type: 'text', disabled: false,
        dataset: {}, classList: classe(), focus() {}, getAttribute() { return null; }});
    const campos = Object.fromEntries(['ano', 'valor-requisitado', 'valor-erro', 'modal-feedback',
        'form-simulacao', 'btn-relatorio-simulacao', 'simulacao-atualidade', 'tbody-resultados',
        'fluxo-credito-resultado', 'caed-data-referencia', 'caed-fonte-demais',
        'caed-data-cobertura', 'caed-cobertura-completa', 'ano-fim-contrato'].map(id => [id, elemento(id)]));
    Object.assign(campos.ano, {value: '2026'});
    campos['valor-requisitado'].value = 'R$ 100,00';
    campos['caed-data-referencia'].value = '2026-10-07';
    campos['caed-fonte-demais'].value = 'Documento real conferido';
    campos['caed-data-cobertura'].value = '2026-10-07';
    campos['caed-cobertura-completa'].checked = true;
    campos['caed-cobertura-completa'].type = 'checkbox';
    campos['ano-fim-contrato'].value = '2026';
    const pagamentos = [elemento('juros', 'R$ 5,00'), elemento('amortizacao', 'R$ 5,00'), elemento('demais', 'R$ 0,00')];
    const linha = {dataset: {ano: '2026'}, querySelectorAll: () => pagamentos};
    const todos = [...Object.values(campos), ...pagamentos];
    const document = {addEventListener() {}, getElementById: id => campos[id],
        querySelector: () => campos['form-simulacao'],
        querySelectorAll: seletor => seletor.includes('[data-ano]') ? [linha] : todos};
    const ctx = vm.createContext({document, console});
    vm.runInContext(script, ctx);
    ctx.mensagens = [];
    ctx.renders = 0;
    ctx.mostrarCarregamento = () => {};
    ctx.mostrarMensagem = m => ctx.mensagens.push(m);
    ctx.renderizarResultados = () => ctx.renders++;
    ctx.mostrarSecao = () => {};
    ctx.obterEntradaMga = () => ({snapshot: campos['valor-requisitado'].value});
    return {ctx, campos, pagamentos, linha};
}

async function validar() {
    const {ctx, campos, pagamentos, linha} = preparar();
    const entrada = ctx.obterEntradaServico();
    assert.equal(entrada.linhas[0].demais_operacoes, '0.00');
    assert.equal(entrada.cobertura_demais.completa, true);
    assert(!('hipotese_2' in entrada));
    pagamentos[2].value = '';
    assert.equal(ctx.obterEntradaServico().linhas[0].demais_operacoes, null);
    pagamentos[2].value = '0,00';
    assert.throws(() => ctx.normalizarPagamentoCaed('1,111'), /duas casas/);
    vm.runInContext('resultadoSimulacaoAtual = {assinatura: assinaturaEntradasSimulacao()}; resultadoDesatualizado = false;', ctx);
    const evento = {clipboardData: {getData: () => '2,00\t3,00\t4,00\n'}, preventDefault() {}};
    ctx.colarPlanilhaServico(evento, {querySelectorAll: () => [linha]}, linha, 0);
    assert.deepEqual(pagamentos.map(p => p.value), ['R$ 2,00', 'R$ 3,00', 'R$ 4,00']);
    assert.equal(campos['btn-relatorio-simulacao'].disabled, true);
    assert.equal(campos['caed-cobertura-completa'].checked, false);
    assert.equal(vm.runInContext('resultadoDesatualizado', ctx), true);

    // Não há espera/salvamento de fator entre a captura dos cronogramas.
    const segundo = preparar();
    let resolver;
    let enviados;
    segundo.ctx.eel = {analisar_operacao_py: (...args) => () => {
        enviados = args;
        return new Promise(resolve => { resolver = resolve; });
    }, salvar_fator_projecao_py() { assert.fail('Fator não deve ser salvo durante cálculo'); }};
    const calculo = segundo.ctx.executarSimulacao();
    assert.equal(enviados[2].linhas[0].juros_encargos, '5.00');
    segundo.pagamentos[0].value = '99,00';
    // Mesmo alteração programática sem evento precisa ser detectada pela assinatura.
    resolver({status: 'Análise completa.', regras_ordenadas: [], regras_violadas: []});
    await calculo;
    assert.equal(segundo.ctx.renders, 0);
    assert(segundo.ctx.mensagens.some(m => m.includes('entradas mudaram')));
    assert.equal(vm.runInContext('resultadoSimulacaoAtual', segundo.ctx), null);
    assert.equal(enviados[2].linhas[0].juros_encargos, '5.00');
    console.log('CAED frontend: grade única, precisão, colagem e captura assíncrona validadas.');
}
validar().catch(erro => { console.error(erro); process.exitCode = 1; });
