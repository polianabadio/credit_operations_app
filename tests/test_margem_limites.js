const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Elemento {
    constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; this.style = {}; }
    append(...nos) { this.children.push(...nos); }
    appendChild(no) { this.children.push(no); return no; }
    setAttribute() {}
    texto() { return [this.textContent, ...this.children.map(no => no.texto())].join(' '); }
}
const ctx = vm.createContext({document: {createElement: tag => new Elemento(tag)},
    formatarMoeda: v => `R$ ${v}`, formatarPercentual: v => `${v}%`});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/web/js/fiscal-dashboard.js'), 'utf8'), ctx);
const config = vm.runInContext('LIMITES_PRINCIPAIS[0]', ctx);
const dado = {limite: 16, fluxo: {ano: 2026, positionOnly: true, parameterValidated: true,
    rows: [{ano: 2026, dadosCompletos: true, margemEstimada: 60, scheduledDisbursements: 100, tetoAnual: 160, rclProjetada: 1000}]}};
let card = ctx.criarResumoLimite(config, dado).texto();
assert(card.includes('Margem disponível no exercício R$ 60'));
assert(!card.includes('Maior comprometimento projetado'));
assert(!card.includes('MGA/RCL'));
let detalhe = ctx.criarDetalheMargemCredito(dado).texto();
assert(detalhe.includes('Liberações existentes incluídas'));
assert(!detalhe.includes('Operação pleiteada'));
assert(!detalhe.includes('MGA ='));
for (const alteracao of [{positionOnly:false}, {parameterValidated:false}]) {
    const parcial = {...dado, fluxo:{...dado.fluxo,...alteracao}};
    assert.equal(ctx.linhaMargemCredito(parcial), null);
    assert(ctx.criarResumoLimite(config, parcial).texto().includes('Não determinada'));
}
dado.fluxo.rows[0].margemEstimada = 0;
assert(ctx.criarResumoLimite(config, dado).texto().includes('R$ 0'));
dado.fluxo.rows[0].margemEstimada = -20;
assert(ctx.criarResumoLimite(config, dado).texto().includes('R$ -20'));
dado.fluxo.rows[0].dadosCompletos = false;
assert.equal(ctx.linhaMargemCredito(dado), null);
assert(ctx.criarDetalheMargemCredito(dado).texto().includes('Não determinada'));
console.log('Margem em Limites: cobertura, parâmetro, zero, saldo negativo e separação da simulação validados.');
const publico = {...dado,margemPublica:{status:'Referência pública',coverageConfirmed:false,
    snapshot:{numeroPvl:'PVL teste'},motivos:['Cobertura não confirmada'],
    rows:[{ano:2026,margemEstimada:160,scheduledDisbursements:0,rclProjetada:1000,tetoAnual:160,
        liberacoesContratadas:0,liberacoesNaoContratadasListadas:0,fonteZero:'indicador_liberacoes=0'}]}};
assert(ctx.criarResumoLimite(config, publico).texto().includes('Margem segundo o PVL R$ 160'));
assert(ctx.criarDetalheMargemCredito(publico).texto().includes('Zero declarado pela fonte'));
assert.equal(ctx.badgeQualidade(publico,'mga')[0], 'Referência SADIPEM · conferir cobertura');
assert.equal(ctx.linhaMargemCredito(publico), null);
const simulacao = {ano:2026, dataAvailability:true, criticalYear:2026, exceededYears:[],
    maxLimitUsage:0.1, validatedConclusion:false, publicReference:{snapshot:{numeroPvl:'PVL teste'}},
    rows:[{ano:2026,requestedOperation:100,scheduledDisbursements:0,mga:100,
        rclProjetada:1000,tetoAnual:160,margemEstimada:60}]};
const textoSimulacao = ctx.criarTabelaMga(simulacao).texto();
assert(textoSimulacao.includes('Dentro do limite de 16% — segundo os dados do PVL'));
assert(textoSimulacao.includes('Saldo após a nova operação R$ 60'));
assert(textoSimulacao.includes('Liberações das demais operações R$ 0'));
assert(!textoSimulacao.includes('Referência pública'));
assert(!textoSimulacao.includes('Margem após outras'));
assert(!textoSimulacao.includes('Uso do limite'));
assert(ctx.resultadoVisualMga({...simulacao,dataAvailability:false}).includes('Inconclusivo'));
assert(ctx.resultadoVisualMga({...simulacao,exceededYears:[2026]}).includes('Acima do limite'));
console.log('Simulação MGA: composição em reais, conclusão separada da fonte e ausência de indicadores redundantes validadas.');
