const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class No {
    constructor() { this.children = []; this.textContent = ''; this.classList = {add() {}}; }
    append(...nos) { this.children.push(...nos); }
    appendChild(no) { this.append(no); return no; }
    replaceChildren() { this.children = []; }
    get texto() { return [this.textContent, ...this.children.map(n => n.texto)].join(' '); }
}
const ids = new Map();
const contexto = vm.createContext({document: {
    addEventListener() {}, createElement: () => new No(),
    getElementById(id) { if (!ids.has(id)) ids.set(id, new No()); return ids.get(id); }
}});
vm.runInContext(fs.readFileSync('src/web/js/eel-main.js', 'utf8'), contexto);
const dados = {
    ano_historico: 2025, rcl_fonte: {valor: 1000, periodo: 3, exercicio: 2026},
    fator_atualizacao: {taxa_percentual: '2.01'}, motivos: [],
    historico: {aprovado: true, rcl: 1000, servico_divida: 115, limite: 115,
        margem: 0, juros_encargos: 15, amortizacao: 100, restos_juros: 0, restos_amortizacao: 0},
    memoria_exata: {historico: {rcl: {valor: '1000', periodo: 6}, despesas: {periodo: 6}}}
};
let tela = new No();
contexto.renderizarServicoDivida({aprovado: true, dados_calculados: dados}, tela);
assert(!tela.texto.includes('não disponível'));
assert(!tela.texto.includes('Pendências da análise'));
assert(!tela.texto.includes('igualdade reprova'));
assert(tela.texto.includes('≤'));
assert(ids.get('servico-dados-base').texto.includes('3º bimestre de 2026'));
assert(ids.get('servico-dados-base').texto.includes('2.01%'));
tela = new No();
contexto.renderizarServicoDivida({aprovado: null, descricao: 'Faltam pagamentos das demais operações.',
    dados_calculados: {...dados, motivos: [{codigo: 'PAGAMENTO_AUSENTE_OU_INVALIDO'}]}}, tela);
assert(tela.texto.includes('Faltam pagamentos das demais operações.'));
assert(!tela.texto.includes('O cálculo não pode continuar'));
console.log('CAED: dados atuais exibidos sem alertas falsos; pendências reais preservadas.');
const publico = {...dados, linhas: [
    {ano: 2026, juros_encargos: 1, amortizacao: 2, demais_operacoes: 0, caed_total: 3, rcl_projetada: 1000, percentual: .003},
    {ano: 2027, juros_encargos: 1, amortizacao: 2, demais_operacoes: null, caed_total: null, rcl_projetada: 1000, percentual: null}
], media_termino: .3, media_2027: .3, percentual_determinante: .3, resultado_numerico: 'ATENDE',
referencia_publica_demais: {fonte: 'SADIPEM / res-cronograma-pagamentos',
    snapshot: {numeroPvl: 'PVL-teste', data: '30/07/2026'}, consultado_em: '2026-10-28', motivos: []}};
contexto.renderizarServicoDivida({aprovado: null, dados_calculados: publico}, new No());
const detalhe = ids.get('servico-resultados').texto;
assert(detalhe.includes('PVL-teste'));
assert(detalhe.includes('Demais dívidas'));
assert(detalhe.includes('Completude do conjunto de dívidas não confirmada pelo usuário'));
assert(detalhe.includes('Não disponível'));
assert(detalhe.includes('Média utilizada'));
const resumo = contexto.resumoLimiteCaed({tipo: 'servico_divida', aprovado: null, dados_calculados: publico});
assert.equal(resumo.rotulo, 'Limite atendido');
assert(!resumo.descricao.includes('Sem informação'));
assert(!resumo.descricao.includes('cobertura'));
assert.equal(contexto.resumoLimiteCaed({aprovado: null, dados_calculados: {}}).rotulo, 'Cálculo incompleto');
assert.equal(contexto.resumoLimiteCaed({aprovado: false, dados_calculados: {percentual_determinante: 12}}).rotulo, 'Limite excedido');
